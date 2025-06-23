const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log(
    "🚀 Deploying CarbonCreditToken smart contract (Production Ready)...\n"
  );

  // Get the contract factory
  const CarbonCreditToken = await ethers.getContractFactory(
    "CarbonCreditToken"
  );

  // Deploy with gas optimization
  console.log("📦 Deploying contract with gas optimization...");

  const carbonCreditToken = await CarbonCreditToken.deploy({
    gasLimit: 6000000, // 6M gas limit for complex deployment
    gasPrice: ethers.parseUnits("2", "gwei"), // 2 gwei for Polygon
  });

  // Wait for deployment to be mined
  await carbonCreditToken.waitForDeployment();

  const contractAddress = await carbonCreditToken.getAddress();

  console.log("✅ CarbonCreditToken deployed to:", contractAddress);
  console.log("🔗 Network:", (await ethers.provider.getNetwork()).name);

  const deploymentTx = carbonCreditToken.deploymentTransaction();
  if (deploymentTx) {
    console.log(
      "⛽ Gas used for deployment:",
      deploymentTx.gasUsed?.toString()
    );
    console.log(
      "💰 Deployment cost:",
      ethers.formatEther(deploymentTx.gasUsed * deploymentTx.gasPrice),
      "MATIC"
    );
  }

  // Save contract details for backend
  const contractInfo = {
    address: contractAddress,
    network: "polygon-amoy",
    deployedAt: new Date().toISOString(),
    deployer: deploymentTx?.from,
    transactionHash: deploymentTx?.hash,
    abi: CarbonCreditToken.interface.format("json"),
    contractType: "CarbonCreditToken",
    version: "1.0.0",
    features: [
      "ERC721 NFT",
      "Gas-optimized batch minting",
      "USDA verification tracking",
      "Credit retirement",
      "Role-based access control",
    ],
  };

  // Create contracts directory in Django backend if it doesn't exist
  const contractsDir = path.join(__dirname, "..", "carbon", "contracts");
  if (!fs.existsSync(contractsDir)) {
    fs.mkdirSync(contractsDir, { recursive: true });
  }

  // Save contract info
  fs.writeFileSync(
    path.join(contractsDir, "CarbonCreditToken.json"),
    JSON.stringify(contractInfo, null, 2)
  );

  console.log(
    "📄 Contract info saved to carbon/contracts/CarbonCreditToken.json"
  );

  // Test contract functionality
  console.log("\n🧪 Testing contract functionality...");

  try {
    // Test getting contract stats
    const stats = await carbonCreditToken.getContractStats();
    console.log("📊 Initial contract stats:", {
      totalCreditsIssued: stats[0].toString(),
      totalCreditsRetired: stats[1].toString(),
      totalCO2eTokenized: stats[2].toString(),
      activeCredits: stats[3].toString(),
    });

    // Test constants
    const maxBatchSize = await carbonCreditToken.MAX_BATCH_SIZE();
    const validityPeriod = await carbonCreditToken.CREDIT_VALIDITY_PERIOD();

    console.log("⚙️ Contract Configuration:", {
      maxBatchSize: maxBatchSize.toString(),
      validityPeriodDays: (validityPeriod / 86400n).toString(), // Convert seconds to days
    });

    // Test role assignments (deployer should have all roles)
    const [deployer] = await ethers.getSigners();
    const hasAdminRole = await carbonCreditToken.hasRole(
      await carbonCreditToken.DEFAULT_ADMIN_ROLE(),
      deployer.address
    );
    const hasMinterRole = await carbonCreditToken.hasRole(
      await carbonCreditToken.MINTER_ROLE(),
      deployer.address
    );

    console.log("👤 Role Assignments:", {
      deployer: deployer.address,
      hasAdminRole,
      hasMinterRole,
    });

    console.log("✅ Contract deployed and tested successfully!");
  } catch (error) {
    console.error("❌ Error testing contract:", error.message);
  }

  console.log("\n📋 Next steps:");
  console.log("1. Add contract address to Django settings:");
  console.log(`   CARBON_CREDIT_CONTRACT_ADDRESS = "${contractAddress}"`);
  console.log("2. Update your environment variables:");
  console.log("   BLOCKCHAIN_NETWORK_NAME = 'polygon_amoy'");
  console.log("3. Test the production blockchain service:");
  console.log("   poetry run python test_blockchain_production.py");
  console.log("\n🔗 View on Polygonscan:");
  console.log(`https://amoy.polygonscan.com/address/${contractAddress}`);

  // Gas optimization recommendations
  console.log("\n⚡ Gas Optimization Recommendations:");
  console.log(
    "- Use batch operations for multiple credits (up to 50 per batch)"
  );
  console.log("- Monitor network congestion for optimal gas pricing");
  console.log("- Consider off-peak hours for large batch operations");
  console.log("- Estimated cost per credit: ~$0.01 on Polygon mainnet");
}

// Handle errors
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });
