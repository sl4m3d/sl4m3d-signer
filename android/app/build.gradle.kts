plugins {
    id("com.android.application")
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

        testInstrumentationRunner =
            "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            isDebuggable = true
        }

        release {
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += setOf(
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE",
                "META-INF/LICENSE.md",
                "META-INF/LICENSE.txt",
                "META-INF/NOTICE",
                "META-INF/NOTICE.md",
                "META-INF/NOTICE.txt"
            )
        }
    }
}

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.86")
    implementation("org.bouncycastle:bcpkix-jdk18on:1.86")

    testImplementation("junit:junit:4.13.2")
}
