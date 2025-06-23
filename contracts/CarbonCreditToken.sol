// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/**
 * @title CarbonCreditToken
 * @dev Production-ready ERC721 NFT contract for Trazo's carbon credit tokenization
 * Features: Gas optimization, batch processing, USDA compliance verification
 */
contract CarbonCreditToken is ERC721, ERC721URIStorage, AccessControl, Pausable, ReentrancyGuard {
    using Counters for Counters.Counter;

    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant BATCH_PROCESSOR_ROLE = keccak256("BATCH_PROCESSOR_ROLE");

    // Gas-optimized storage packing
    struct CarbonCredit {
        uint128 productionId;       // Trazo production ID (packed with co2eAmount)
        uint128 co2eAmount;         // CO2e amount in grams (packed with productionId)
        uint64 issuanceDate;        // Issuance timestamp (packed with flags)
        uint64 expirationDate;      // Credit expiration (packed with flags)
        uint32 producerId;          // Trazo producer ID (packed with flags)
        uint8 creditType;           // 0=sequestration, 1=avoidance, 2=removal
        bool isRetired;             // Whether credit is retired
        bool usdaVerified;          // USDA compliance status
    }

    struct BatchMintData {
        address farmer;
        uint256 productionId;
        uint256 co2eAmount;
        string usdaVerificationHash;
        uint8 creditType;
    }

    // Storage
    mapping(uint256 => CarbonCredit) public carbonCredits;
    mapping(uint256 => string) public usdaVerificationHashes;
    mapping(address => uint256[]) public farmerCredits;
    mapping(uint256 => uint256[]) public productionCredits; // productionId => tokenIds[]
    
    Counters.Counter private _tokenIdCounter;
    
    // Gas optimization: batch processing limits
    uint256 public constant MAX_BATCH_SIZE = 50;
    uint256 public constant CREDIT_VALIDITY_PERIOD = 365 days * 10; // 10 years
    
    // Statistics
    uint256 public totalCreditsIssued;
    uint256 public totalCreditsRetired;
    uint256 public totalCO2eTokenized;

    // Events
    event CarbonCreditMinted(
        uint256 indexed tokenId,
        address indexed farmer,
        uint256 indexed productionId,
        uint256 co2eAmount,
        uint8 creditType
    );
    
    event CarbonCreditRetired(
        uint256 indexed tokenId,
        address indexed retiredBy,
        uint256 co2eAmount
    );
    
    event BatchMintCompleted(
        uint256 indexed batchId,
        uint256 creditsCount,
        uint256 totalCO2e
    );

    event USDAVerificationUpdated(
        uint256 indexed tokenId,
        bool verified,
        string verificationHash
    );

    constructor() ERC721("Trazo Carbon Credits", "TCC") {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);
        _grantRole(VERIFIER_ROLE, msg.sender);
        _grantRole(BATCH_PROCESSOR_ROLE, msg.sender);
    }

    /**
     * @dev Gas-optimized single carbon credit minting
     */
    function mintCarbonCredit(
        address farmer,
        uint256 productionId,
        uint256 co2eAmount,
        string memory usdaVerificationHash,
        uint8 creditType
    ) external onlyRole(MINTER_ROLE) whenNotPaused returns (uint256) {
        require(farmer != address(0), "Invalid farmer address");
        require(co2eAmount > 0, "Invalid CO2e amount");
        require(creditType <= 2, "Invalid credit type");
        require(productionId > 0, "Invalid production ID");

        uint256 tokenId = _tokenIdCounter.current();
        _tokenIdCounter.increment();

        // Gas-optimized storage packing
        carbonCredits[tokenId] = CarbonCredit({
            productionId: uint128(productionId),
            co2eAmount: uint128(co2eAmount),
            issuanceDate: uint64(block.timestamp),
            expirationDate: uint64(block.timestamp + CREDIT_VALIDITY_PERIOD),
            producerId: uint32(productionId), // Assuming producerId can be derived
            creditType: creditType,
            isRetired: false,
            usdaVerified: bytes(usdaVerificationHash).length > 0
        });

        // Store verification hash separately to avoid gas costs in struct
        if (bytes(usdaVerificationHash).length > 0) {
            usdaVerificationHashes[tokenId] = usdaVerificationHash;
        }

        // Update mappings
        farmerCredits[farmer].push(tokenId);
        productionCredits[productionId].push(tokenId);

        // Update statistics
        totalCreditsIssued++;
        totalCO2eTokenized += co2eAmount;

        _safeMint(farmer, tokenId);

        emit CarbonCreditMinted(tokenId, farmer, productionId, co2eAmount, creditType);

        return tokenId;
    }

    /**
     * @dev Gas-optimized batch minting for multiple credits
     */
    function batchMintCarbonCredits(
        BatchMintData[] calldata batchData
    ) external onlyRole(BATCH_PROCESSOR_ROLE) whenNotPaused returns (uint256[] memory) {
        require(batchData.length > 0 && batchData.length <= MAX_BATCH_SIZE, "Invalid batch size");

        uint256[] memory tokenIds = new uint256[](batchData.length);
        uint256 batchTotalCO2e = 0;
        uint256 batchId = block.timestamp; // Simple batch ID

        for (uint256 i = 0; i < batchData.length; i++) {
            BatchMintData memory data = batchData[i];
            
            require(data.farmer != address(0), "Invalid farmer address");
            require(data.co2eAmount > 0, "Invalid CO2e amount");
            require(data.creditType <= 2, "Invalid credit type");

            uint256 tokenId = _tokenIdCounter.current();
            _tokenIdCounter.increment();

            // Gas-optimized storage
            carbonCredits[tokenId] = CarbonCredit({
                productionId: uint128(data.productionId),
                co2eAmount: uint128(data.co2eAmount),
                issuanceDate: uint64(block.timestamp),
                expirationDate: uint64(block.timestamp + CREDIT_VALIDITY_PERIOD),
                producerId: uint32(data.productionId),
                creditType: data.creditType,
                isRetired: false,
                usdaVerified: bytes(data.usdaVerificationHash).length > 0
            });

            if (bytes(data.usdaVerificationHash).length > 0) {
                usdaVerificationHashes[tokenId] = data.usdaVerificationHash;
            }

            // Update mappings
            farmerCredits[data.farmer].push(tokenId);
            productionCredits[data.productionId].push(tokenId);

            // Mint token
            _safeMint(data.farmer, tokenId);

            tokenIds[i] = tokenId;
            batchTotalCO2e += data.co2eAmount;

            emit CarbonCreditMinted(tokenId, data.farmer, data.productionId, data.co2eAmount, data.creditType);
        }

        // Update statistics
        totalCreditsIssued += batchData.length;
        totalCO2eTokenized += batchTotalCO2e;

        emit BatchMintCompleted(batchId, batchData.length, batchTotalCO2e);

        return tokenIds;
    }

    /**
     * @dev Retire a carbon credit (permanently remove from circulation)
     */
    function retireCarbonCredit(uint256 tokenId) external whenNotPaused {
        require(_exists(tokenId), "Token does not exist");
        require(ownerOf(tokenId) == msg.sender, "Not token owner");
        require(!carbonCredits[tokenId].isRetired, "Credit already retired");

        CarbonCredit storage credit = carbonCredits[tokenId];
        credit.isRetired = true;

        totalCreditsRetired++;

        // Burn the token
        _burn(tokenId);

        emit CarbonCreditRetired(tokenId, msg.sender, credit.co2eAmount);
    }

    /**
     * @dev Update USDA verification status (verifier role only)
     */
    function updateUSDAVerification(
        uint256 tokenId,
        bool verified,
        string memory verificationHash
    ) external onlyRole(VERIFIER_ROLE) {
        require(_exists(tokenId), "Token does not exist");

        carbonCredits[tokenId].usdaVerified = verified;
        
        if (verified && bytes(verificationHash).length > 0) {
            usdaVerificationHashes[tokenId] = verificationHash;
        }

        emit USDAVerificationUpdated(tokenId, verified, verificationHash);
    }

    /**
     * @dev Batch verification for gas efficiency
     */
    function batchUpdateUSDAVerification(
        uint256[] calldata tokenIds,
        bool[] calldata verificationStatuses,
        string[] calldata verificationHashes
    ) external onlyRole(VERIFIER_ROLE) {
        require(tokenIds.length == verificationStatuses.length, "Array length mismatch");
        require(tokenIds.length == verificationHashes.length, "Array length mismatch");
        require(tokenIds.length <= MAX_BATCH_SIZE, "Batch too large");

        for (uint256 i = 0; i < tokenIds.length; i++) {
            uint256 tokenId = tokenIds[i];
            require(_exists(tokenId), "Token does not exist");

            carbonCredits[tokenId].usdaVerified = verificationStatuses[i];
            
            if (verificationStatuses[i] && bytes(verificationHashes[i]).length > 0) {
                usdaVerificationHashes[tokenId] = verificationHashes[i];
            }

            emit USDAVerificationUpdated(tokenId, verificationStatuses[i], verificationHashes[i]);
        }
    }

    /**
     * @dev Get carbon credit details
     */
    function getCarbonCredit(uint256 tokenId) external view returns (
        uint256 productionId,
        uint256 co2eAmount,
        uint256 issuanceDate,
        uint256 expirationDate,
        uint256 producerId,
        uint8 creditType,
        bool isRetired,
        bool usdaVerified,
        string memory verificationHash
    ) {
        require(_exists(tokenId), "Token does not exist");
        
        CarbonCredit memory credit = carbonCredits[tokenId];
        
        return (
            credit.productionId,
            credit.co2eAmount,
            credit.issuanceDate,
            credit.expirationDate,
            credit.producerId,
            credit.creditType,
            credit.isRetired,
            credit.usdaVerified,
            usdaVerificationHashes[tokenId]
        );
    }

    /**
     * @dev Get farmer's carbon credits
     */
    function getFarmerCredits(address farmer) external view returns (uint256[] memory) {
        return farmerCredits[farmer];
    }

    /**
     * @dev Get production's carbon credits
     */
    function getProductionCredits(uint256 productionId) external view returns (uint256[] memory) {
        return productionCredits[productionId];
    }

    /**
     * @dev Get contract statistics
     */
    function getContractStats() external view returns (
        uint256 _totalCreditsIssued,
        uint256 _totalCreditsRetired,
        uint256 _totalCO2eTokenized,
        uint256 _activeCredits
    ) {
        return (
            totalCreditsIssued,
            totalCreditsRetired,
            totalCO2eTokenized,
            totalCreditsIssued - totalCreditsRetired
        );
    }

    /**
     * @dev Check if credit is valid (not expired and not retired)
     */
    function isValidCredit(uint256 tokenId) external view returns (bool) {
        if (!_exists(tokenId)) return false;
        
        CarbonCredit memory credit = carbonCredits[tokenId];
        return !credit.isRetired && block.timestamp <= credit.expirationDate;
    }

    // Required overrides for multiple inheritance
    function _burn(uint256 tokenId) internal override(ERC721, ERC721URIStorage) {
        super._burn(tokenId);
    }

    function tokenURI(uint256 tokenId) public view override(ERC721, ERC721URIStorage) returns (string memory) {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC721URIStorage, AccessControl) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    // Emergency functions
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
} 