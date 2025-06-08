// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title CarbonVerification
 * @dev Smart contract for Trazo's carbon verification and credit system
 * Stores monthly carbon summaries and issues carbon credits for verified sustainable practices
 */
contract CarbonVerification is AccessControl, Pausable, ReentrancyGuard {
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");
    
    // USDA compliance thresholds (in grams CO2e per kg of product)
    uint256 public constant USDA_CITRUS_THRESHOLD = 2000;  // 2.0 kg CO2e/kg
    uint256 public constant USDA_ALMOND_THRESHOLD = 2100;  // 2.1 kg CO2e/kg  
    uint256 public constant USDA_SOYBEAN_THRESHOLD = 400;  // 0.4 kg CO2e/kg
    uint256 public constant USDA_GENERAL_THRESHOLD = 1000; // 1.0 kg CO2e/kg

    struct CarbonRecord {
        bytes32 dataHash;           // SHA-256 hash of carbon data
        uint256 producerId;         // Trazo producer ID
        uint256 productionId;       // Trazo production ID
        uint256 totalEmissions;     // Total emissions in grams CO2e
        uint256 totalOffsets;       // Total offsets in grams CO2e
        int256 netFootprint;        // Net footprint (can be negative)
        uint256 entryCount;         // Number of carbon entries
        string cropType;            // Type of crop produced
        uint256 timestamp;          // Block timestamp
        bool usdaCompliant;         // Whether meets USDA standards
        bool creditsIssued;         // Whether carbon credits were issued
        uint256 creditsAmount;      // Amount of credits issued
    }

    struct Producer {
        address walletAddress;      // Producer's wallet
        bool isActive;              // Active status
        uint256 totalCredits;       // Total credits earned
        uint256 recordCount;        // Number of records
        uint256 joinDate;           // Date joined platform
    }

    // Storage
    mapping(uint256 => CarbonRecord) public carbonRecords;          // productionId => CarbonRecord
    mapping(uint256 => Producer) public producers;                  // producerId => Producer
    mapping(uint256 => uint256[]) public producerRecords;           // producerId => productionIds[]
    mapping(bytes32 => bool) public usedHashes;                     // Prevent hash reuse
    
    uint256 public totalRecords;
    uint256 public totalCreditsIssued;
    uint256 public totalProducers;

    // Events
    event MonthlySummaryRecorded(
        uint256 indexed productionId,
        uint256 indexed producerId,
        bytes32 dataHash,
        int256 netFootprint,
        bool usdaCompliant
    );
    
    event ComplianceVerified(
        uint256 indexed productionId,
        bool compliant,
        string cropType,
        uint256 threshold
    );
    
    event CreditsIssued(
        uint256 indexed productionId,
        uint256 indexed producerId,
        uint256 creditsAmount
    );

    event ProducerRegistered(
        uint256 indexed producerId,
        address indexed walletAddress
    );

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(VERIFIER_ROLE, msg.sender);
        _grantRole(AUDITOR_ROLE, msg.sender);
    }

    /**
     * @dev Register a new producer with their wallet address
     */
    function registerProducer(
        uint256 producerId,
        address walletAddress
    ) external onlyRole(VERIFIER_ROLE) {
        require(producers[producerId].walletAddress == address(0), "Producer already registered");
        require(walletAddress != address(0), "Invalid wallet address");

        producers[producerId] = Producer({
            walletAddress: walletAddress,
            isActive: true,
            totalCredits: 0,
            recordCount: 0,
            joinDate: block.timestamp
        });

        totalProducers++;
        emit ProducerRegistered(producerId, walletAddress);
    }

    /**
     * @dev Record monthly carbon summary for a production
     */
    function recordMonthlySummary(
        bytes32 dataHash,
        uint256 producerId,
        uint256 productionId,
        uint256 totalEmissions,
        uint256 totalOffsets,
        string calldata cropType
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused nonReentrant {
        require(!usedHashes[dataHash], "Data hash already used");
        require(producers[producerId].isActive, "Producer not active");
        require(bytes(cropType).length > 0, "Invalid crop type");
        require(carbonRecords[productionId].timestamp == 0, "Record already exists");

        // Calculate net footprint (can be negative for carbon negative)
        int256 netFootprint = int256(totalEmissions) - int256(totalOffsets);

        // Check USDA compliance based on crop type
        bool usdaCompliant = _checkUsdaCompliance(cropType, uint256(netFootprint));

        // Create carbon record
        carbonRecords[productionId] = CarbonRecord({
            dataHash: dataHash,
            producerId: producerId,
            productionId: productionId,
            totalEmissions: totalEmissions,
            totalOffsets: totalOffsets,
            netFootprint: netFootprint,
            entryCount: 0, // Will be updated separately if needed
            cropType: cropType,
            timestamp: block.timestamp,
            usdaCompliant: usdaCompliant,
            creditsIssued: false,
            creditsAmount: 0
        });

        // Update producer records
        producerRecords[producerId].push(productionId);
        producers[producerId].recordCount++;
        
        // Mark hash as used
        usedHashes[dataHash] = true;
        totalRecords++;

        emit MonthlySummaryRecorded(productionId, producerId, dataHash, netFootprint, usdaCompliant);
        emit ComplianceVerified(productionId, usdaCompliant, cropType, _getThresholdForCrop(cropType));

        // Auto-issue credits if carbon negative and USDA compliant
        if (netFootprint < 0 && usdaCompliant) {
            _issueCredits(productionId, uint256(-netFootprint));
        }
    }

    /**
     * @dev Issue carbon credits for verified carbon negative production
     */
    function issueCredits(
        uint256 productionId,
        uint256 creditsAmount
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        CarbonRecord storage record = carbonRecords[productionId];
        require(record.timestamp > 0, "Record does not exist");
        require(record.usdaCompliant, "Not USDA compliant");
        require(record.netFootprint < 0, "Not carbon negative");
        require(!record.creditsIssued, "Credits already issued");

        _issueCredits(productionId, creditsAmount);
    }

    /**
     * @dev Internal function to issue credits
     */
    function _issueCredits(uint256 productionId, uint256 creditsAmount) internal {
        CarbonRecord storage record = carbonRecords[productionId];
        Producer storage producer = producers[record.producerId];

        record.creditsIssued = true;
        record.creditsAmount = creditsAmount;
        producer.totalCredits += creditsAmount;
        totalCreditsIssued += creditsAmount;

        emit CreditsIssued(productionId, record.producerId, creditsAmount);
    }

    /**
     * @dev Check USDA compliance based on crop type and net footprint
     */
    function _checkUsdaCompliance(string memory cropType, uint256 netFootprint) internal pure returns (bool) {
        uint256 threshold = _getThresholdForCrop(cropType);
        return netFootprint <= threshold;
    }

    /**
     * @dev Get USDA threshold for specific crop type
     */
    function _getThresholdForCrop(string memory cropType) internal pure returns (uint256) {
        bytes32 cropHash = keccak256(abi.encodePacked(cropType));
        
        if (cropHash == keccak256(abi.encodePacked("citrus")) || 
            cropHash == keccak256(abi.encodePacked("orange"))) {
            return USDA_CITRUS_THRESHOLD;
        } else if (cropHash == keccak256(abi.encodePacked("almond"))) {
            return USDA_ALMOND_THRESHOLD;
        } else if (cropHash == keccak256(abi.encodePacked("soybean"))) {
            return USDA_SOYBEAN_THRESHOLD;
        }
        
        return USDA_GENERAL_THRESHOLD; // Default threshold
    }

    /**
     * @dev Get carbon record by production ID
     */
    function getCarbonRecord(uint256 productionId) external view returns (CarbonRecord memory) {
        require(carbonRecords[productionId].timestamp > 0, "Record does not exist");
        return carbonRecords[productionId];
    }

    /**
     * @dev Get producer information
     */
    function getProducer(uint256 producerId) external view returns (Producer memory) {
        return producers[producerId];
    }

    /**
     * @dev Get producer's production records
     */
    function getProducerRecords(uint256 producerId) external view returns (uint256[] memory) {
        return producerRecords[producerId];
    }

    /**
     * @dev Verify data integrity by checking hash
     */
    function verifyDataIntegrity(
        uint256 productionId,
        string calldata originalData
    ) external view returns (bool) {
        CarbonRecord memory record = carbonRecords[productionId];
        require(record.timestamp > 0, "Record does not exist");
        
        bytes32 computedHash = keccak256(abi.encodePacked(originalData));
        return computedHash == record.dataHash;
    }

    /**
     * @dev Get contract statistics
     */
    function getContractStats() external view returns (
        uint256 _totalRecords,
        uint256 _totalCreditsIssued,
        uint256 _totalProducers
    ) {
        return (totalRecords, totalCreditsIssued, totalProducers);
    }

    /**
     * @dev Emergency pause (admin only)
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @dev Resume operations (admin only)
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /**
     * @dev Update producer status (admin only)
     */
    function updateProducerStatus(
        uint256 producerId,
        bool isActive
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(producers[producerId].walletAddress != address(0), "Producer not found");
        producers[producerId].isActive = isActive;
    }
} 