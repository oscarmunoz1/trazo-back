const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log(
    "🚀 Deploying CarbonVerification smart contract to Polygon Amoy Testnet...\n"
  );

  // Get the contract factory
  const CarbonVerification = await ethers.getContractFactory(
    "CarbonVerification"
  );

  // Deploy the contract
  console.log("📦 Deploying contract...");
  const carbonVerification = await CarbonVerification.deploy();

  // Wait for deployment to be mined
  await carbonVerification.waitForDeployment();

  const contractAddress = await carbonVerification.getAddress();

  console.log("✅ CarbonVerification deployed to:", contractAddress);
  console.log("🔗 Network:", (await ethers.provider.getNetwork()).name);
  console.log(
    "⛽ Gas used for deployment:",
    await carbonVerification.deploymentTransaction().gasUsed?.toString()
  );

  // Save contract details for backend
  const contractInfo = {
    address: contractAddress,
    network: "polygon-amoy",
    deployedAt: new Date().toISOString(),
    deployer: await carbonVerification.deploymentTransaction().from,
    transactionHash: carbonVerification.deploymentTransaction().hash,
    abi: CarbonVerification.interface.format("json"),
  };

  // Create contracts directory in Django backend if it doesn't exist
  const contractsDir = path.join(__dirname, "..", "carbon", "contracts");
  if (!fs.existsSync(contractsDir)) {
    fs.mkdirSync(contractsDir, { recursive: true });
  }

  // Save contract info
  fs.writeFileSync(
    path.join(contractsDir, "CarbonVerification.json"),
    JSON.stringify(contractInfo, null, 2)
  );

  console.log(
    "📄 Contract info saved to carbon/contracts/CarbonVerification.json"
  );

  // Test contract functionality
  console.log("\n🧪 Testing contract functionality...");

  try {
    // Test getting contract stats
    const stats = await carbonVerification.getContractStats();
    console.log("📊 Initial contract stats:", {
      totalRecords: stats[0].toString(),
      totalCreditsIssued: stats[1].toString(),
      totalProducers: stats[2].toString(),
    });

    // Test USDA thresholds
    const citrusThreshold = await carbonVerification.USDA_CITRUS_THRESHOLD();
    const almondThreshold = await carbonVerification.USDA_ALMOND_THRESHOLD();
    const soybeanThreshold = await carbonVerification.USDA_SOYBEAN_THRESHOLD();

    console.log("🌱 USDA Thresholds (grams CO2e/kg):", {
      citrus: citrusThreshold.toString(),
      almond: almondThreshold.toString(),
      soybean: soybeanThreshold.toString(),
    });

    console.log("✅ Contract deployed and tested successfully!");
  } catch (error) {
    console.error("❌ Error testing contract:", error.message);
  }

  console.log("\n📋 Next steps:");
  console.log("1. Add contract address to Django settings:");
  console.log(`   CARBON_CONTRACT_ADDRESS = "${contractAddress}"`);
  console.log("2. Add your Alchemy RPC URL to settings:");
  console.log(
    "   POLYGON_RPC_URL = 'https://polygon-amoy.g.alchemy.com/v2/YOUR_KEY'"
  );
  console.log("3. Add your wallet private key to settings (keep secure!):");
  console.log("   BLOCKCHAIN_PRIVATE_KEY = 'your_private_key'");
  console.log("\n🔗 View on Polygonscan:");
  console.log(`https://amoy.polygonscan.com/address/${contractAddress}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });
