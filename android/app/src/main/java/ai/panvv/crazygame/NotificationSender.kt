package ai.panvv.crazygame

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.net.URLEncoder
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object NotificationSender {
    private val client = OkHttpClient()

    fun send(channel: JSONObject, title: String, body: String): JSONObject {
        return when (channel.optString("type")) {
            "feishu" -> sendFeishu(channel.optJSONObject("config") ?: JSONObject(), title, body)
            "aliyun_sms" -> sendAliyunSms(
                channel.optJSONObject("config") ?: JSONObject(),
                title,
                body
            )
            else -> JSONObject().put("ok", false).put("error", "unsupported_channel")
        }
    }

    private fun sendFeishu(config: JSONObject, title: String, body: String): JSONObject {
        val webhook = config.optString("webhook_url")
        if (webhook.isBlank()) return JSONObject().put("ok", false).put("error", "missing_webhook")
        val payload = JSONObject()
            .put("msg_type", "text")
            .put("content", JSONObject().put("text", "$title\n$body"))
        val secret = config.optString("secret")
        if (secret.isNotBlank()) {
            val timestamp = System.currentTimeMillis().toString()
            val sign = hmac(
                "HmacSHA256",
                "$timestamp\n$secret".toByteArray(),
                ByteArray(0)
            )
            payload.put("timestamp", timestamp).put("sign", sign)
        }
        val request = Request.Builder()
            .url(webhook)
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        return execute(request)
    }

    private fun sendAliyunSms(config: JSONObject, title: String, body: String): JSONObject {
        val accessKeyId = config.optString("access_key_id")
        val accessSecret = config.optString("access_key_secret")
        val phones = config.optString("phone_numbers")
        val signName = config.optString("sign_name")
        val template = config.optString("template_code_zh")
            .ifBlank { config.optString("template_code_en") }
        if (listOf(accessKeyId, accessSecret, phones, signName, template).any { it.isBlank() }) {
            return JSONObject().put("ok", false).put("error", "missing_sms_config")
        }
        val parameters = linkedMapOf(
            "AccessKeyId" to accessKeyId,
            "Action" to "SendSms",
            "Format" to "JSON",
            "PhoneNumbers" to phones,
            "RegionId" to "cn-hangzhou",
            "SignName" to signName,
            "SignatureMethod" to "HMAC-SHA1",
            "SignatureNonce" to UUID.randomUUID().toString(),
            "SignatureVersion" to "1.0",
            "TemplateCode" to template,
            "TemplateParam" to JSONObject()
                .put("title", title.take(20))
                .put("content", body.take(80))
                .toString(),
            "Timestamp" to DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'")
                .withZone(ZoneOffset.UTC)
                .format(Instant.now()),
            "Version" to "2017-05-25"
        )
        val canonical = parameters.entries
            .sortedBy { it.key }
            .joinToString("&") { "${percentEncode(it.key)}=${percentEncode(it.value)}" }
        val stringToSign = "GET&%2F&${percentEncode(canonical)}"
        val signature = hmac(
            "HmacSHA1",
            "${accessSecret}&".toByteArray(),
            stringToSign.toByteArray()
        )
        val query = "$canonical&Signature=${percentEncode(signature)}"
        val request = Request.Builder()
            .url("https://dysmsapi.aliyuncs.com/?$query")
            .get()
            .build()
        return execute(request)
    }

    private fun execute(request: Request): JSONObject {
        return runCatching {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                val parsed = runCatching { JSONObject(text) }.getOrDefault(JSONObject())
                val ok = response.isSuccessful &&
                    (parsed.optString("Code").isBlank() || parsed.optString("Code") == "OK") &&
                    (parsed.optInt("code", 0) == 0)
                JSONObject()
                    .put("ok", ok)
                    .put("status", response.code)
                    .put("body", text)
            }
        }.getOrElse { error ->
            JSONObject().put("ok", false).put("error", error.message ?: "send_failed")
        }
    }

    private fun hmac(algorithm: String, key: ByteArray, value: ByteArray): String {
        val mac = Mac.getInstance(algorithm)
        mac.init(SecretKeySpec(key, algorithm))
        return android.util.Base64.encodeToString(mac.doFinal(value), android.util.Base64.NO_WRAP)
    }

    private fun percentEncode(value: String): String =
        URLEncoder.encode(value, "UTF-8")
            .replace("+", "%20")
            .replace("*", "%2A")
            .replace("%7E", "~")
}
