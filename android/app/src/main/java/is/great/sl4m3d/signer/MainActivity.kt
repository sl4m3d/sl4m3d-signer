
package `is`.great.sl4m3d.signer

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.bouncycastle.asn1.x500.X500Name
import org.bouncycastle.asn1.x500.RDN
import org.bouncycastle.asn1.x500.style.BCStyle
import org.bouncycastle.asn1.DERUTF8String
import org.bouncycastle.cert.X509CertificateHolder
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.cms.CMSProcessableByteArray
import org.bouncycastle.cms.CMSSignedData
import org.bouncycastle.cms.CMSSignedDataGenerator
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder
import org.bouncycastle.cert.jcajce.JcaCertStore
import org.bouncycastle.jce.provider.BouncyCastleProvider
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder
import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Security
import java.security.cert.X509Certificate
import java.util.Date

class MainActivity : Activity() {

    private val bg = Color.rgb(10, 14, 18)
    private val panel = Color.rgb(17, 25, 32)
    private val fg = Color.rgb(216, 227, 232)
    private val muted = Color.rgb(132, 146, 154)
    private val accent = Color.rgb(255, 180, 84)

    private lateinit var main: LinearLayout
    private lateinit var commonName: EditText
    private lateinit var validDays: EditText
    private lateinit var p12Password: EditText
    private lateinit var cerOnly: CheckBox
    private lateinit var profileName: EditText
    private lateinit var profileId: EditText
    private lateinit var webclipUrl: EditText
    private lateinit var status: TextView

    private var pendingCer: ByteArray? = null
    private var pendingP12: ByteArray? = null
    private var inputBytes: ByteArray? = null
    private var inputName: String = "document"
    private var identity: KeyPair? = null
    private var identityCert: X509Certificate? = null
    private var pendingCms: ByteArray? = null
    private var pendingExtract: ByteArray? = null

    companion object {
        private const val PICK_INPUT = 100
        private const val PICK_P12 = 101
        private const val SAVE_CER = 102
        private const val SAVE_P12 = 103
        private const val SAVE_CMS = 104
        private const val PICK_CMS = 105
        private const val SAVE_EXTRACT = 106
        private const val SAVE_PROFILE = 107
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Security.removeProvider("BC")
        Security.insertProviderAt(BouncyCastleProvider(), 1)

        buildUi()
    }

    private fun buildUi() {
        val scroll = ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            isVerticalScrollBarEnabled = true
            scrollBarStyle = View.SCROLLBARS_INSIDE_INSET
        }

        main = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(26), dp(22), dp(32))
            setBackgroundColor(bg)
        }

        scroll.addView(main)
        setContentView(scroll)

        text(main, "sl4m3d", 32, fg, true)
        text(main, "SIGNER / CERTIFICATES / CMS / LOCAL FILES", 11, accent)
        text(main, "Offline first · Private Daten bleiben auf diesem Gerät", 12, muted)

        status = text(
            main,
            "Bereit · Keine Netzwerkberechtigung erforderlich",
            12,
            muted
        )

        section("Zertifikat erstellen")

        commonName = field(
            "Common Name",
            "sl4m3d local certificate"
        )

        validDays = field(
            "Gültigkeit in Tagen (1–3650)",
            "365",
            numeric = true
        )

        p12Password = field(
            "P12-Passwort (mindestens 8 Zeichen bei CER + P12)",
            "",
            password = true
        )

        cerOnly = CheckBox(this).apply {
            text = "Nur öffentliche .cer-Datei exportieren"
            setTextColor(fg)
            buttonTintList =
                android.content.res.ColorStateList.valueOf(accent)
            isChecked = true
        }

        main.addView(cerOnly)

        button("CER / P12 ERSTELLEN") {
            createCertificate()
        }

        section("Dateien signieren")

        button("DATEI AUSWÄHLEN") {
            pickFile(PICK_INPUT, "application/octet-stream")
        }

        button("P12 / PFX IDENTITÄT AUSWÄHLEN") {
            pickFile(PICK_P12, "application/x-pkcs12")
        }

        button("CMS-SIGNATUR ERSTELLEN") {
            signSelectedFile()
        }

        text(
            main,
            "Eine .cer-Datei enthält keinen privaten Schlüssel. " +
                "Zum Signieren wird eine passende .p12/.pfx-Identität benötigt.",
            11,
            muted
        )

        section("Signatur prüfen")

        button("CMS-DATEI AUSWÄHLEN") {
            pickFile(PICK_CMS, "application/pkcs7-mime")
        }

        button("CMS PRÜFEN UND INHALT SPEICHERN") {
            verifySelectedCms()
        }

        section(".mobileconfig")

        profileName = field(
            "Profilname",
            "sl4m3d Configuration"
        )

        profileId = field(
            "Eindeutige Identifier-Kennung",
            "is.great.sl4m3d.profile"
        )

        webclipUrl = field(
            "Web Clip URL (optional)",
            "https://sl4m3d.xo.je"
        )

        button("XML-PROFIL ERSTELLEN") {
            createProfile()
        }

        section("Update-Log")

        text(
            main,
            "v1.2.0 · 07.11.2026\n" +
                "Scrollbare Android-Oberfläche, CER-only und CER+P12, " +
                "lokale Dateiauswahl, CMS-Signieren und -Prüfen, " +
                ".mobileconfig-Basisprofil, keine Internetberechtigung.\n\n" +
                "v1.1.0 · 06.11.2026\n" +
                "Lokale X.509-/CMS-Funktionen und Apple-Konfigurationsprofile.",
            12,
            fg
        )

        text(
            main,
            "Android-Buildstatus: Quellprojekt. APK muss auf einem " +
                "Android-SDK-Runner gebaut und getestet werden.",
            11,
            muted
        )
    }

    private fun section(label: String) {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(14))
            setBackgroundColor(panel)
        }

        val title = TextView(this).apply {
            text = label.uppercase()
            textSize = 13f
            setTextColor(accent)
            setPadding(0, 0, 0, dp(6))
        }

        box.addView(title)

        main.addView(
            box,
            LinearLayout.LayoutParams(-1, -2).apply {
                topMargin = dp(20)
            }
        )
    }

    private fun text(
        parent: LinearLayout,
        value: String,
        size: Int,
        color: Int,
        bold: Boolean = false
    ): TextView {
        val view = TextView(this).apply {
            text = value
            textSize = size.toFloat()
            setTextColor(color)

            if (bold) {
                setTypeface(
                    typeface,
                    android.graphics.Typeface.BOLD
                )
            }

            setPadding(0, dp(4), 0, dp(4))
        }

        parent.addView(view)
        return view
    }

    private fun field(
        label: String,
        value: String,
        numeric: Boolean = false,
        password: Boolean = false
    ): EditText {
        text(main, label.uppercase(), 10, accent)

        val edit = EditText(this).apply {
            setText(value)
            setTextColor(fg)
            setHintTextColor(muted)
            textSize = 14f
            setSingleLine(true)
            setPadding(dp(12), dp(7), dp(12), dp(7))
            setBackgroundColor(panel)

            if (numeric) {
                inputType = InputType.TYPE_CLASS_NUMBER
            }

            if (password) {
                inputType =
                    InputType.TYPE_CLASS_TEXT or
                    InputType.TYPE_TEXT_VARIATION_PASSWORD
            }
        }

        main.addView(
            edit,
            LinearLayout.LayoutParams(-1, dp(48)).apply {
                bottomMargin = dp(8)
            }
        )

        return edit
    }

    private fun button(
        label: String,
        action: () -> Unit
    ) {
        val btn = Button(this).apply {
            text = label
            setTextColor(bg)
            setBackgroundTintList(
                android.content.res.ColorStateList.valueOf(accent)
            )
            isAllCaps = false

            setOnClickListener {
                runCatching(action).onFailure {
                    showError(it)
                }
            }
        }

        main.addView(
            btn,
            LinearLayout.LayoutParams(-1, -2).apply {
                topMargin = dp(7)
            }
        )
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).toInt()
    }

    private fun pickFile(code: Int, mime: String) {
        startActivityForResult(
            Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = mime
            },
            code
        )
    }

    private fun createDocument(
        code: Int,
        mime: String,
        fileName: String
    ) {
        startActivityForResult(
            Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = mime
                putExtra(Intent.EXTRA_TITLE, fileName)
            },
            code
        )
    }

    private fun readUri(uri: Uri): ByteArray {
        val size = contentResolver.query(
            uri,
            arrayOf(OpenableColumns.SIZE),
            null,
            null,
            null
        )?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) else -1L
        } ?: -1L

        require(
            size <= 64L * 1024 * 1024 || size < 0
        ) {
            "Dateien über 64 MiB werden in dieser Android-Version nicht geladen."
        }

        val bytes = contentResolver.openInputStream(uri)?.use {
            it.readBytes()
        } ?: error("Datei konnte nicht gelesen werden.")

        require(bytes.size <= 64 * 1024 * 1024) {
            "Dateien über 64 MiB werden in dieser Android-Version nicht geladen."
        }

        return bytes
    }

    private fun writeUri(uri: Uri, bytes: ByteArray) {
        contentResolver.openOutputStream(uri, "wt")?.use {
            it.write(bytes)
            it.flush()
        } ?: error("Zieldatei konnte nicht geschrieben werden.")
    }

    private fun createCertificate() {
        val cn = commonName.text.toString().trim()

        require(cn.isNotBlank()) {
            "Common Name darf nicht leer sein."
        }

        val days = validDays.text.toString().toIntOrNull()
            ?: error("Ungültige Gültigkeit.")

        require(days in 1..3650) {
            "Gültigkeit muss zwischen 1 und 3650 Tagen liegen."
        }

        val includeP12 = !cerOnly.isChecked
        val pass = p12Password.text.toString()

        if (includeP12) {
            require(pass.length >= 8) {
                "P12-Passwort muss mindestens 8 Zeichen haben."
            }
        }

        val algorithm = KeyPairGenerator.getInstance("RSA", "BC")
        algorithm.initialize(3072)

        val pair = algorithm.generateKeyPair()

        val subject = X500Name(
            arrayOf(
                RDN(
                    BCStyle.CN,
                    DERUTF8String(cn)
                )
            )
        )

        val now = System.currentTimeMillis()

        val serial = BigInteger(159, java.security.SecureRandom())
            .abs()
            .add(BigInteger.ONE)

        val builder = JcaX509v3CertificateBuilder(
            subject,
            serial,
            Date(now - 60_000),
            Date(now + days * 86_400_000L),
            subject,
            pair.public
        )

        builder.addExtension(
            org.bouncycastle.asn1.x509.Extension.basicConstraints,
            true,
            org.bouncycastle.asn1.x509.BasicConstraints(false)
        )

        builder.addExtension(
            org.bouncycastle.asn1.x509.Extension.keyUsage,
            true,
            org.bouncycastle.asn1.x509.KeyUsage(
                org.bouncycastle.asn1.x509.KeyUsage.digitalSignature or
                    org.bouncycastle.asn1.x509.KeyUsage.keyEncipherment
            )
        )

        val signer = JcaContentSignerBuilder("SHA256withRSA")
            .setProvider("BC")
            .build(pair.private)

        val cert = JcaX509CertificateConverter()
            .setProvider("BC")
            .getCertificate(builder.build(signer))

        cert.checkValidity(Date())
        cert.verify(pair.public)

        pendingCer = cert.encoded
        pendingP12 = if (includeP12) {
            createP12(pair, cert, pass)
        } else {
            null
        }

        p12Password.setText("")

        createDocument(
            SAVE_CER,
            "application/pkix-cert",
            safeName(cn) + ".cer"
        )
    }

    private fun createP12(
        pair: KeyPair,
        cert: X509Certificate,
        password: String
    ): ByteArray {
        val store = KeyStore.getInstance("PKCS12", "BC")

        store.load(null, null)

        store.setKeyEntry(
            "sl4m3d",
            pair.private,
            password.toCharArray(),
            arrayOf(cert)
        )

        return ByteArrayOutputStream().use { out ->
            store.store(out, password.toCharArray())
            out.toByteArray()
        }
    }

    private fun signSelectedFile() {
        val source = inputBytes
            ?: error("Wähle zuerst eine zu signierende Datei aus.")

        val pair = identity
            ?: error("Wähle zuerst eine passende P12/PFX-Identität aus.")

        val cert = identityCert
            ?: error("Zertifikat fehlt in der Identität.")

        val generator = CMSSignedDataGenerator()

        val algorithm =
            if (
                pair.private.algorithm.equals("EC", true) ||
                pair.private.algorithm.equals("ECDSA", true)
            ) {
                "SHA256withECDSA"
            } else {
                "SHA256withRSA"
            }

        val contentSigner = JcaContentSignerBuilder(algorithm)
            .setProvider("BC")
            .build(pair.private)

        val digestProvider =
            JcaDigestCalculatorProviderBuilder()
                .setProvider("BC")
                .build()

        generator.addSignerInfoGenerator(
            JcaSignerInfoGeneratorBuilder(digestProvider)
                .build(contentSigner, cert)
        )

        generator.addCertificates(
            JcaCertStore(listOf(cert))
        )

        val signed = generator.generate(
            CMSProcessableByteArray(source),
            true
        ).encoded

        val parsed = CMSSignedData(signed)

        check(parsed.signerInfos.signers.isNotEmpty()) {
            "Signatur enthält keine Signer."
        }

        check(parsed.signedContent.content is ByteArray) {
            "CMS-Inhalt fehlt."
        }

        pendingCms = signed

        createDocument(
            SAVE_CMS,
            "application/pkcs7-mime",
            safeName(inputName) + ".signed.p7m"
        )
    }

    private fun loadIdentity(
        p12: ByteArray,
        password: String
    ) {
        val store = KeyStore.getInstance("PKCS12", "BC")

        store.load(
            p12.inputStream(),
            password.toCharArray()
        )

        val alias = store.aliases().toList()
            .firstOrNull { store.isKeyEntry(it) }
            ?: error("Keine private Identität in P12 gefunden.")

        val key = store.getKey(
            alias,
            password.toCharArray()
        ) as? java.security.PrivateKey
            ?: error("Privater Schlüssel fehlt.")

        val cert = store.getCertificate(alias) as? X509Certificate
            ?: error("X.509-Zertifikat fehlt.")

        val algorithm =
            if (key.algorithm.equals("EC", true)) {
                "SHA256withECDSA"
            } else {
                "SHA256withRSA"
            }

        val challenge = "sl4m3d-p12-key-pair-check"
            .toByteArray(Charsets.UTF_8)

        val proof = java.security.Signature
            .getInstance(algorithm, "BC")
            .run {
                initSign(key)
                update(challenge)
                sign()
            }

        val matches = java.security.Signature
            .getInstance(algorithm, "BC")
            .run {
                initVerify(cert.publicKey)
                update(challenge)
                verify(proof)
            }

        require(matches) {
            "P12-Privatschlüssel passt nicht zum Zertifikat."
        }

        identity = KeyPair(cert.publicKey, key)
        identityCert = cert

        status.text =
            "P12-Identität lokal geladen und Schlüsseltyp geprüft."
    }

    private fun verifySelectedCms() {
        val bytes = inputBytes
            ?: error("Wähle zuerst eine CMS-Datei aus.")

        val signed = CMSSignedData(bytes)
        val signers = signed.signerInfos.signers

        require(signers.isNotEmpty()) {
            "CMS enthält keine Signatur."
        }

        val store = signed.certificates
        var valid = false

        for (signer in signers) {
            // Zertifikate aus dem CMS laden und anhand der Signer-ID zuordnen.
            val certificates = store.getMatches(null)

            val holder: X509CertificateHolder =
                certificates.firstOrNull { certificate ->
                    signer.sid.match(certificate)
                } ?: continue

            val ok = signer.verify(
                JcaSimpleSignerInfoVerifierBuilder()
                    .setProvider("BC")
                    .build(holder)
            )

            if (ok) {
                valid = true
            }
        }

        require(valid) {
            "CMS-Signatur ist ungültig oder das Zertifikat stimmt nicht überein."
        }

        val content = signed.signedContent?.content as? ByteArray
            ?: error("Signatur enthält keinen eingebetteten Inhalt.")

        pendingExtract = content

        createDocument(
            SAVE_EXTRACT,
            "application/octet-stream",
            safeName(inputName) + ".verified"
        )
    }

    private fun createProfile() {
        val name = profileName.text.toString().trim()
        val identifier = profileId.text.toString().trim()

        require(name.isNotBlank() && identifier.isNotBlank()) {
            "Profilname und Identifier dürfen nicht leer sein."
        }

        val url = webclipUrl.text.toString().trim()

        val clipPayload = if (url.isNotBlank()) {
            val parsed = android.net.Uri.parse(url)

            require(
                parsed.scheme == "https" || parsed.scheme == "http"
            ) {
                "Web Clip URL muss HTTP oder HTTPS verwenden."
            }

            require(!parsed.host.isNullOrBlank()) {
                "Web Clip URL benötigt einen Hostnamen."
            }

            """
            <dict>
            <key>FullScreen</key><false/>
            <key>IsRemovable</key><true/>
            <key>Label</key><string>${xmlEscape(name)}</string>
            <key>PayloadDescription</key><string>Web Clip</string>
            <key>PayloadDisplayName</key><string>${xmlEscape(name)}</string>
            <key>PayloadIdentifier</key><string>${xmlEscape(identifier)}.webclip</string>
            <key>PayloadType</key><string>com.apple.webClip.managed</string>
            <key>PayloadUUID</key><string>${java.util.UUID.randomUUID()}</string>
            <key>PayloadVersion</key><integer>1</integer>
            <key>URL</key><string>${xmlEscape(url)}</string>
            </dict>
            """.trimIndent()
        } else {
            ""
        }

        val payload = """
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
            <key>PayloadContent</key><array>$clipPayload</array>
            <key>PayloadDescription</key><string>Generated locally by sl4m3d Signer</string>
            <key>PayloadDisplayName</key><string>${xmlEscape(name)}</string>
            <key>PayloadIdentifier</key><string>${xmlEscape(identifier)}</string>
            <key>PayloadOrganization</key><string>sl4m3d</string>
            <key>PayloadType</key><string>Configuration</string>
            <key>PayloadUUID</key><string>${java.util.UUID.randomUUID()}</string>
            <key>PayloadVersion</key><integer>1</integer>
            <key>PayloadScope</key><string>System</string>
            </dict>
            </plist>
        """.trimIndent()

        pendingExtract = payload.toByteArray(Charsets.UTF_8)

        createDocument(
            SAVE_PROFILE,
            "application/x-apple-aspen-config",
            safeName(name) + ".mobileconfig"
        )
    }

    @Deprecated("Deprecated in Android API")
    override fun onActivityResult(
        requestCode: Int,
        resultCode: Int,
        data: Intent?
    ) {
        super.onActivityResult(requestCode, resultCode, data)

        if (resultCode != RESULT_OK) return

        val uri = data?.data ?: return

        try {
            when (requestCode) {

                PICK_INPUT -> {
                    inputBytes = readUri(uri)
                    inputName =
                        uri.lastPathSegment?.substringAfterLast('/')
                            ?: "document"

                    status.text =
                        "Dokument lokal ausgewählt: $inputName"
                }

                PICK_CMS -> {
                    inputBytes = readUri(uri)
                    inputName =
                        uri.lastPathSegment?.substringAfterLast('/')
                            ?: "signature.p7m"

                    status.text = "CMS-Datei lokal ausgewählt."
                }

                PICK_P12 -> {
                    val p12 = readUri(uri)

                    passwordDialog("P12-Passwort") { pass ->
                        runCatching {
                            loadIdentity(p12, pass)
                        }.onFailure {
                            showError(it)
                        }
                    }
                }

                SAVE_CER -> {
                    val bytes = pendingCer
                        ?: error("Interner CER-Export fehlt.")

                    writeUri(uri, bytes)
                    pendingCer = null

                    status.text = "DER-.cer exportiert."

                    val p12 = pendingP12

                    if (p12 != null) {
                        createDocument(
                            SAVE_P12,
                            "application/x-pkcs12",
                            "sl4m3d-identity.p12"
                        )
                    } else {
                        status.text =
                            "CER-only abgeschlossen; kein privater Schlüssel exportiert."
                    }
                }

                SAVE_P12 -> {
                    writeUri(
                        uri,
                        pendingP12 ?: error("P12-Export fehlt.")
                    )

                    pendingP12 = null
                    status.text =
                        "CER + passwortgeschützte P12-Identität exportiert."
                }

                SAVE_CMS -> {
                    writeUri(
                        uri,
                        pendingCms ?: error("CMS-Export fehlt.")
                    )

                    pendingCms = null
                    status.text =
                        "CMS erzeugt und eingebetteter Inhalt geprüft."
                }

                SAVE_EXTRACT -> {
                    writeUri(
                        uri,
                        pendingExtract ?: error("Prüf-Inhalt fehlt.")
                    )

                    pendingExtract = null

                    status.text =
                        "CMS-Signatur gültig; Inhalt lokal extrahiert. " +
                        "Zertifikatsvertrauen wurde nicht bewertet."
                }

                SAVE_PROFILE -> {
                    writeUri(
                        uri,
                        pendingExtract ?: error("Profilinhalt fehlt.")
                    )

                    pendingExtract = null

                    status.text =
                        ".mobileconfig XML-Plist exportiert. " +
                        "Profil ist nicht CMS-signiert."
                }
            }
        } catch (e: Exception) {
            showError(e)
        }
    }

    private fun passwordDialog(
        title: String,
        result: (String) -> Unit
    ) {
        val edit = EditText(this).apply {
            inputType =
                InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_VARIATION_PASSWORD
        }

        AlertDialog.Builder(this)
            .setTitle(title)
            .setView(edit)
            .setNegativeButton("Abbrechen", null)
            .setPositiveButton("Weiter") { _, _ ->
                result(edit.text.toString())
            }
            .show()
    }

    private fun xmlEscape(value: String): String {
        return value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
    }

    private fun safeName(value: String): String {
        return value
            .map {
                if (it.isLetterOrDigit() || it in "-_ ") it else '_'
            }
            .joinToString("")
            .trim()
            .take(64)
            .ifBlank { "signer" }
    }

    private fun showError(e: Throwable) {
        status.text =
            "Fehler: ${e.message ?: e.javaClass.simpleName}"

        AlertDialog.Builder(this)
            .setTitle("Aktion fehlgeschlagen")
            .setMessage(e.message ?: "Unbekannter Fehler")
            .setPositiveButton("OK", null)
            .show()
    }
}
