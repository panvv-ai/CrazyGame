package ai.panvv.crazygame

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class DailyReviewWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val now = Instant.now().atZone(ZoneId.of("Asia/Shanghai"))
        if (now.dayOfWeek.value >= 6) return Result.success()
        if (now.hour < 15 || (now.hour == 15 && now.minute < 20)) return Result.success()

        val store = CrazyGameStore(applicationContext)
        val state = runCatching { JSONObject(store.readState()) }.getOrElse {
            return Result.success()
        }
        val settings = state.optJSONObject("settings") ?: return Result.success()
        if (!settings.optBoolean("daily_review_enabled", true)) return Result.success()
        val holdings = state.optJSONArray("holdings") ?: return Result.success()
        if (holdings.length() == 0) return Result.success()
        val tradeDate = now.format(DateTimeFormatter.ISO_LOCAL_DATE)
        val reviews = state.optJSONArray("reviews") ?: JSONArray().also {
            state.put("reviews", it)
        }
        for (index in 0 until reviews.length()) {
            val review = reviews.optJSONObject(index) ?: continue
            if (review.optString("trade_date") == tradeDate && review.optString("status") == "success") {
                return Result.success()
            }
        }
        val ai = settings.optJSONObject("ai") ?: return Result.success()
        val baseUrl = ai.optString("base_url").trimEnd('/')
        val apiKey = ai.optString("api_key")
        val model = ai.optString("model")
        if (baseUrl.isBlank() || apiKey.isBlank() || model.isBlank()) return Result.success()

        val instruments = buildMap {
            val rows = state.optJSONArray("instruments") ?: JSONArray()
            for (index in 0 until rows.length()) {
                val instrument = rows.optJSONObject(index) ?: continue
                put(instrument.optInt("id"), instrument)
            }
        }
        val snapshot = JSONArray()
        for (index in 0 until holdings.length()) {
            val holding = holdings.optJSONObject(index) ?: continue
            val instrument = instruments[holding.optInt("instrument_id")] ?: continue
            val quote = runCatching { AlertQuotes.fetch(instrument) }.getOrNull()
            snapshot.put(
                JSONObject()
                    .put("symbol", instrument.optString("symbol"))
                    .put("name", instrument.optString("name"))
                    .put("market", instrument.optString("market"))
                    .put("quantity", holding.optDouble("quantity"))
                    .put("average_cost", holding.optDouble("average_cost"))
                    .put("current_price", quote?.optDouble("current_price"))
                    .put("change_pct", quote?.optDouble("change_pct"))
            )
        }
        val messages = JSONArray()
            .put(
                JSONObject()
                    .put("role", "system")
                    .put(
                        "content",
                        "Create a concise daily portfolio health review in Markdown. Discuss concentration, trend, hold/watch/reduce/add observations, and include a disclaimer. Do not predict prices."
                    )
            )
            .put(
                JSONObject()
                    .put("role", "user")
                    .put("content", snapshot.toString())
            )
        val payload = JSONObject()
            .put("model", model)
            .put("messages", messages)
        val request = Request.Builder()
            .url("$baseUrl/chat/completions")
            .header("Authorization", "Bearer $apiKey")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        val content = runCatching {
            OkHttpClient().newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@use ""
                val text = response.body?.string().orEmpty()
                JSONObject(text)
                    .optJSONArray("choices")
                    ?.optJSONObject(0)
                    ?.optJSONObject("message")
                    ?.optString("content")
                    .orEmpty()
            }
        }.getOrDefault("")
        if (content.isBlank()) return Result.retry()

        val title = if (settings.optString("language") == "en-US") {
            "Daily portfolio health"
        } else {
            "每日持仓健康简报"
        }
        val review = JSONObject()
            .put("id", System.currentTimeMillis())
            .put("trade_date", tradeDate)
            .put("language", settings.optString("language", "zh-CN"))
            .put("status", "success")
            .put("title", title)
            .put("content", content)
            .put("snapshot_json", snapshot.toString())
            .put("model_label", model)
            .put("notified_at", Instant.now().toString())
            .put("error", "")
            .put("created_at", Instant.now().toString())
        reviews.put(review)
        store.writeState(state.toString())
        postNotification(title, content.take(180))
        sendRemote(settings, title, content.take(500), state)
        return Result.success()
    }

    private fun sendRemote(settings: JSONObject, title: String, content: String, state: JSONObject) {
        val selected = settings.optJSONArray("daily_review_channel_ids") ?: JSONArray()
        val channels = state.optJSONArray("channels") ?: JSONArray()
        for (index in 0 until channels.length()) {
            val channel = channels.optJSONObject(index) ?: continue
            if (channel.optString("type") == "local" || !channel.optBoolean("enabled", true)) continue
            val included = (0 until selected.length()).any {
                selected.optInt(it) == channel.optInt("id")
            }
            if (included) NotificationSender.send(channel, title, content)
        }
    }

    private fun postNotification(title: String, body: String) {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    applicationContext.getString(R.string.notification_channel_name),
                    NotificationManager.IMPORTANCE_DEFAULT
                )
            )
        }
        manager.notify(
            (System.currentTimeMillis() and 0x7fffffff).toInt(),
            NotificationCompat.Builder(applicationContext, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .build()
        )
    }

    companion object {
        const val UNIQUE_NAME = "crazygame-daily-review"
        private const val CHANNEL_ID = "crazygame_alerts"
    }
}
