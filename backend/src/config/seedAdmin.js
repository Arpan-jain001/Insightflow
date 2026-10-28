import mongoose from "mongoose";
import dotenv from "dotenv";
import User from "../models/User.js";

dotenv.config();

const seedAdmin = async () => {
  const email = process.env.ADMIN_EMAIL?.trim().toLowerCase();
  if (!email) {
    throw new Error("ADMIN_EMAIL must be configured");
  }

  try {
    await mongoose.connect(process.env.MONGO_URI);

    const existing = await User.findOne({ email });

    if (existing) {
      existing.role = "SUPER_ADMIN";
      existing.status = "ACTIVE";
      existing.verificationStatus = "VERIFIED";
      await existing.save();
      console.log("✅ Existing user promoted to Super Admin");
      console.log("📧 Email:", existing.email);
      return;
    }

    if (!process.env.ADMIN_PASSWORD) {
      throw new Error("ADMIN_PASSWORD must be configured to create the admin");
    }

    const admin = new User({
      name: process.env.ADMIN_NAME || "Super Admin",
      email,
      password: process.env.ADMIN_PASSWORD,
      role: "SUPER_ADMIN",
      status: "ACTIVE",
      verificationStatus: "VERIFIED",
    });

    await admin.save(); // ⚠️ important (create ki jagah save)

    console.log("✅ Super Admin Created Successfully");
    console.log("📧 Email:", admin.email);
  } catch (error) {
    console.error("❌ FULL ERROR:", error);
    process.exitCode = 1;
  } finally {
    await mongoose.disconnect();
  }
};

seedAdmin();