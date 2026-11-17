package ai.panvv.crazygame

import android.Manifest
import android.app.Activity
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.pm.PackageManager
import android.os.Build
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.core.app.NotificationCompat
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.nio.charset.Charset
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class NativeBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    private val store: CrazyGameStore
) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()
    private val executor = Executors.newCachedThreadPool()
    private val calls = ConcurrentHashMap<String, okhttp3.Call>()

    @JavascriptInterface
    fun readState(): String = store.readState()

    @JavascriptInterface
    fun writeState(value: String): Boolean = runCatching {
        store.writeState(value)
        true
    }.getOrDefault(false)

    @JavascriptInterface
    fun request(
        id: String,
        method: String,
        url: String,
        headersJson: String,
        body: String
    ) {
        executor.execute {
            val result = JSONObject()
            try {
                val headers = JSONObject(headersJson.ifBlank { "{}" })
                val builder = Request.Builder().url(url)
                headers.keys().forEach { key ->
                    builder.header(key, headers.optString(key))
                }
                val requestBody = when (method.uppercase()) {
                    "POST", "PUT", "PATCH", "DELETE" ->
                        body.toRequestBody("application/json; charset=utf-8".toMediaType())
                    else -> null
                }
                val request = builder.method(method.uppercase(), requestBody).build()
                val call = client.newCall(request)
                calls[id] = call
                call.execute().use { response ->
                    val bytes = response.body!!.bytes()
                    val text = if (url.contains("qt.gtimg.cn")) {
                        bytes.toString(Charset.forName("GBK"))
                    } else {
                        bytes.toString(Charsets.UTF_8)
                    }
                    result.put("status", response.code)
                    result.put("body", text)
                }
            } catch (error: Exception) {
                result.put("status", 0)
                result.put("body", "")
                result.put("error", error.message ?: error.javaClass.simpleName)
            } finally {
                calls.remove(id)
                resolveRequest(id, result.toString())
            }
        }
    }

    @JavascriptInterface
    fun cancelRequest(id: String) {
        calls.remove(id)?.cancel()
    }

    @JavascriptInterface
    fun streamAi(
        id: String,
        messagesJson: String,
        vision: Boolean,
        configJson: String
    ) {
        executor.execute {
            try {
                val config = JSONObject(configJson.ifBlank { "{}" })
                val baseUrl = config.optString("base_url").trimEnd('/')
                val apiKey = config.optString("api_key")
                val model = if (vision) {
                    config.optString("vision_model").ifBlank { config.optString("model") }
                } else {
                    config.optString("model")
                }
                if (baseUrl.isBlank() || apiKey.isBlank() || model.isBlank()) {
                    emitAi(id, JSONObject().put("type", "error").put("code", "ai_not_configured"))
                    return@execute
                }
                val payload = JSONObject()
                    .put("model", model)
                    .put("stream", true)
                    .put("messages", JSONArray(messagesJson))
                val request = Request.Builder()
                    .url("$baseUrl/chat/completions")
                    .header("Authorization", "Bearer $apiKey")
                    .header("Content-Type", "application/json")
                    .post(payload.toString().toRequestBody("application/json".toMediaType()))
                    .build()
                val call = client.newCall(request)
                calls[id] = call
                call.execute().use { response ->
                    if (!response.isSuccessful) {
                        val code = when (response.code) {
                            401, 403 -> "ai_auth_failed"
                            429 -> "ai_rate_limited"
                            else -> "ai_provider_error"
                        }
                        emitAi(id, JSONObject().put("type", "error").put("code", code))
                        return@execute
                    }
                    val source = response.body!!.source()
                    var emitted = false
                    source.use { bufferedSource ->
                        while (!bufferedSource.exhausted()) {
                            val line = bufferedSource.readUtf8Line() ?: break
                            if (!line.startsWith("data:")) continue
                            val data = line.removePrefix("data:").trim()
                            if (data == "[DONE]") break
                            val parsed = runCatching { JSONObject(data) }.getOrNull() ?: continue
                            val content = parsed.optJSONArray("choices")
                                ?.optJSONObject(0)
                                ?.optJSONObject("delta")
                                ?.optString("content")
                                .orEmpty()
                            if (content.isNotEmpty()) {
                                emitted = true
                                emitAi(
                                    id,
                                    JSONObject()
                                        .put("type", "delta")
                                        .put("content", content)
                                )
                            }
                        }
                    }
                    emitAi(
                        id,
                        JSONObject()
                            .put("type", "done")
                            .put("content", if (emitted) "" else "")
                    )
                }
            } catch (error: Exception) {
                emitAi(
                    id,
                    JSONObject()
                        .put("type", "error")
                        .put("code", if (error is java.net.SocketTimeoutException) "ai_timeout" else "ai_unreachable")
                )
            } finally {
                calls.remove(id)
            }
        }
    }

    @JavascriptInterface
    fun notify(title: String, body: String) {
        val manager = activity.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 33 &&
            activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 41)
            return
        }
        val channel = NotificationChannel(
            CHANNEL_ID,
            activity.getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = activity.getString(R.string.notification_channel_description)
        }
        manager.createNotificationChannel(channel)
        val notification = NotificationCompat.Builder(activity, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .build()
        manager.notify((System.currentTimeMillis() and 0x7fffffff).toInt(), notification)
    }

    @JavascriptInterface
    fun sendNotification(channelJson: String, title: String, body: String): String =
        NotificationSender.send(JSONObject(channelJson), title, body).toString()

    @JavascriptInterface
    fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
            activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 41)
        }
    }

    @JavascriptInterface
    fun scheduleAlerts(enabled: Boolean, intervalMinutes: Int) {
        val manager = WorkManager.getInstance(activity)
        if (!enabled) {
            manager.cancelUniqueWork(AlertWorker.UNIQUE_NAME)
        } else {
            val request = PeriodicWorkRequestBuilder<AlertWorker>(
                intervalMinutes.coerceAtLeast(15).toLong(),
                TimeUnit.MINUTES
            )
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()
            manager.enqueueUniquePeriodicWork(
                AlertWorker.UNIQUE_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
            )
        }
        val reviewRequest = PeriodicWorkRequestBuilder<DailyReviewWorker>(
            intervalMinutes.coerceAtLeast(15).toLong(),
            TimeUnit.MINUTES
        )
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()
        manager.enqueueUniquePeriodicWork(
            DailyReviewWorker.UNIQUE_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            reviewRequest
        )
    }

    @JavascriptInterface
    fun exportState(value: String, password: String): String {
        return runCatching {
            activity.exportData(value, password)
        }.getOrElse { error ->
            JSONObject().put("ok", false).put("error", error.message ?: "export_failed").toString()
        }
    }

    @JavascriptInterface
    fun importState(value: String, password: String): String {
        return runCatching {
            activity.importData(value, password)
        }.getOrElse { error ->
            JSONObject().put("ok", false).put("error", error.message ?: "import_failed").toString()
        }
    }

    private fun resolveRequest(id: String, resultJson: String) {
        val argument = JSONObject.quote(resultJson)
        webView.post {
            webView.evaluateJavascript(
                "window.__crazygameNativeResolve && window.__crazygameNativeResolve(${JSONObject.quote(id)}, $argument)",
                null
            )
        }
    }

    private fun emitAi(id: String, event: JSONObject) {
        val eventArgument = JSONObject.quote(event.toString())
        webView.post {
            webView.evaluateJavascript(
                "window.__crazygameNativeAiEvent && window.__crazygameNativeAiEvent(${JSONObject.quote(id)}, $eventArgument)",
                null
            )
        }
    }

    companion object {
        private const val CHANNEL_ID = "crazygame_alerts"
    }
}
