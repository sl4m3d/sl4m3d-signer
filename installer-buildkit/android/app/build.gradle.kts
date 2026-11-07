plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "is.great.sl4m3d.signer"
    compileSdk = 36

    defaultConfig {
        applicationId = "is.great.sl4m3d.signer"
        minSdk = 26
        targetSdk = 35
        versionCode = 10200
        versionName = "1.2.0"
    }
}

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.86")
    implementation("org.bouncycastle:bcpkix-jdk18on:1.86")
    testImplementation("junit:junit:4.13.2")
}
