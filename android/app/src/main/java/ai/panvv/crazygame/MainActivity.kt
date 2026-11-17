package ai.panvv.crazygame

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.ViewGroup
import android.view.WindowInsets
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var store: CrazyGameStore
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 30) {
            window.setDecorFitsSystemWindows(false)
            window.statusBarColor = Color.TRANSPARENT
            window.navigationBarColor = Color.TRANSPARENT
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility =
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE or
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                android.view.View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        }
        store = CrazyGameStore(this)
        webView = WebView(this).apply {
            setBackgroundColor(Color.rgb(7, 10, 18))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = true
            settings.allowContentAccess = false
            settings.allowFileAccessFromFileURLs = true
            settings.allowUniversalAccessFromFileURLs = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
            settings.loadWithOverviewMode = false
            settings.useWideViewPort = true
            settings.cacheMode = WebSettings.LOAD_DEFAULT
            if (BuildConfig.DEBUG) WebView.setWebContentsDebuggingEnabled(true)
            addJavascriptInterface(NativeBridge(this@MainActivity, this, store), "CrazyGameNative")
            webViewClient = WebViewClient()
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    view: WebView,
                    callback: ValueCallback<Array<Uri>>,
                    params: FileChooserParams
                ): Boolean {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = callback
                    return try {
                        startActivityForResult(params.createIntent(), FILE_CHOOSER_REQUEST)
                        true
                    } catch (_: Exception) {
                        fileCallback = null
                        false
                    }
                }
            }
            setOnApplyWindowInsetsListener { view, insets ->
                val bars = insets.getInsets(
                    WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()
                )
                (view.layoutParams as? ViewGroup.MarginLayoutParams)?.let { params ->
                    params.setMargins(bars.left, bars.top, bars.right, bars.bottom)
                    view.layoutParams = params
                }
                insets
            }
        }
        setContentView(
            webView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
        if (Build.VERSION.SDK_INT >= 33) {
            onBackInvokedDispatcher.registerOnBackInvokedCallback(
                android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT
            ) {
                handleBack()
            }
        }
        webView.loadUrl("file:///android_asset/web/index.html#/")
    }

    override fun onBackPressed() {
        if (Build.VERSION.SDK_INT < 33) handleBack()
    }

    private fun handleBack() {
        webView.evaluateJavascript(
            """
            (() => {
              const event = new Event('crazygame:back', { cancelable: true });
              window.dispatchEvent(event);
              return event.defaultPrevented;
            })()
            """.trimIndent()
        ) { handled ->
            if (handled != "true") {
                if (webView.canGoBack()) webView.goBack()
                else moveTaskToBack(true)
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode != FILE_CHOOSER_REQUEST) {
            super.onActivityResult(requestCode, resultCode, data)
            return
        }
        val callback = fileCallback
        fileCallback = null
        callback?.onReceiveValue(
            if (resultCode == RESULT_OK) {
                WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            } else {
                null
            }
        )
    }

    fun exportData(value: String, password: String): String {
        if (password.length < 8) throw IllegalArgumentException("password_too_short")
        val salt = ByteArray(16).also(SecureRandom()::nextBytes)
        val iv = ByteArray(12).also(SecureRandom()::nextBytes)
        val key = passwordKey(password, salt)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv))
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        val payload = JSONObject()
            .put("format", "crazygame-transfer")
            .put("version", 1)
            .put("salt", android.util.Base64.encodeToString(salt, android.util.Base64.NO_WRAP))
            .put("iv", android.util.Base64.encodeToString(iv, android.util.Base64.NO_WRAP))
            .put("data", android.util.Base64.encodeToString(encrypted, android.util.Base64.NO_WRAP))
        val directory = File(cacheDir, "exports").apply { mkdirs() }
        val file = File(directory, "CrazyGame-backup.crazygame")
        file.writeText(payload.toString())
        runOnUiThread {
            val uri = FileProvider.getUriForFile(
                this,
                "$packageName.files",
                file
            )
            val share = Intent(Intent.ACTION_SEND).apply {
                type = "application/octet-stream"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(Intent.createChooser(share, "CrazyGame backup"))
        }
        return JSONObject().put("ok", true).put("path", file.absolutePath).toString()
    }

    fun importData(value: String, password: String): String {
        if (value.isBlank()) throw IllegalStateException("backup_empty")
        val payload = JSONObject(value)
        val salt = android.util.Base64.decode(payload.getString("salt"), android.util.Base64.NO_WRAP)
        val iv = android.util.Base64.decode(payload.getString("iv"), android.util.Base64.NO_WRAP)
        val encrypted = android.util.Base64.decode(payload.getString("data"), android.util.Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, passwordKey(password, salt), GCMParameterSpec(128, iv))
        val state = cipher.doFinal(encrypted).toString(Charsets.UTF_8)
        JSONObject(state)
        store.writeState(state)
        return JSONObject().put("ok", true).put("state", state).toString()
    }

    private fun passwordKey(password: String, salt: ByteArray): SecretKeySpec {
        val spec = PBEKeySpec(password.toCharArray(), salt, 210_000, 256)
        val bytes = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            .generateSecret(spec)
            .encoded
        return SecretKeySpec(bytes, "AES")
    }

    companion object {
        private const val FILE_CHOOSER_REQUEST = 81
    }
}
