# Native Android project (v1.2.0)

This is a native Kotlin/Android project with an offline-first, scrollable UI and local X.509, PKCS#12, CMS and `.mobileconfig` operations. It uses the Android Storage Access Framework for file selection and output and declares no `INTERNET` permission. The APK is **not included** because no Android SDK/Gradle Android toolchain is installed in the current Linux build environment.

## Build APK

Use Android Studio or a Linux/macOS/Windows machine with JDK 17, Android SDK API 36, Gradle 9.6+ and Android Gradle Plugin 9.3.1:

```sh
gradle --no-daemon assembleDebug
```

The installable test APK is created at `app/build/outputs/apk/debug/app-debug.apk`. It is a debug-signed test build, not a Play Store release. A public release requires a persistent owner-controlled signing key; do not use a temporary CI key for a public release.

## Important limitation

This initial Android implementation provides a focused native feature set. It does not yet provide every desktop feature (batch queue, full certificate chain UI and desktop-style local library). CMS and certificate verification checks signature integrity; they do not establish a trusted platform certificate chain. P12 private key material stays in app memory while the user performs the selected operation and is not uploaded.
