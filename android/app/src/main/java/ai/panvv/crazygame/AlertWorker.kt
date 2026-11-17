package ai.panvv.crazygame

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

class AlertWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val store = CrazyGameStore(applicationContext)
        val state = runCatching { JSONObject(store.readState()) }.getOrElse {
            return Result.success()
        }
        val alerts = state.optJSONArray("alerts") ?: JSONArray()
        val instruments = state.optJSONArray("instruments") ?: JSONArray()
        val instrumentById = buildMap {
            for (index in 0 until instruments.length()) {
                val instrument = instruments.optJSONObject(index) ?: continue
                put(instrument.optInt("id"), instrument)
            }
        }
        val now = Instant.now()
        val hits = state.optJSONArray("alert_hits") ?: JSONArray().also {
            state.put("alert_hits", it)
        }
        for (index in 0 until alerts.length()) {
            val rule = alerts.optJSONObject(index) ?: continue
            if (!rule.optBoolean("enabled", true)) continue
            val instrument = instrumentById[rule.optInt("instrument_id")] ?: continue
            if (rule.optBoolean("market_hours_only", true) &&
                !isMarketOpen(instrument.optString("market"), now)
            ) continue
            val lastTriggered = rule.optString("last_triggered_at")
                .takeIf { it.isNotBlank() }
                ?.let { runCatching { Instant.parse(it) }.getOrNull() }
            if (rule.optBoolean("once_per_day", true) && lastTriggered != null) {
                val zone = marketZone(instrument.optString("market"))
                if (lastTriggered.atZone(zone).toLocalDate() == now.atZone(zone).toLocalDate()) {
                    continue
                }
            } else if (lastTriggered != null) {
                val cooldown = rule.optInt("cooldown_minutes", 30)
                if (now.epochSecond - lastTriggered.epochSecond < cooldown * 60L) continue
            }
            val quote = runCatching { AlertQuotes.fetch(instrument) }.getOrNull() ?: continue
            val observed = if (rule.optString("metric") == "price") {
                quote.optDouble("current_price", Double.NaN)
            } else {
                quote.optDouble("change_pct", Double.NaN)
            }
            if (!observed.isFinite()) continue
            val threshold = rule.optDouble("threshold")
            val matched = if (rule.optString("direction") == "above") {
                observed > threshold
            } else {
                observed < threshold
            }
            if (!matched) continue
            rule.put("last_triggered_at", now.toString())
            hits.put(
                JSONObject()
                    .put("id", System.currentTimeMillis())
                    .put("rule_id", rule.optInt("id"))
                    .put("instrument_id", instrument.optInt("id"))
                    .put("triggered_at", now.toString())
                    .put("observed_value", observed)
                    .put("snapshot", quote)
            )
            postNotification(
                rule.optString("name").ifBlank { instrument.optString("name") },
                "${instrument.optString("name")} $observed"
            )
            val channelIds = rule.optJSONArray("channel_ids") ?: JSONArray()
            val channels = state.optJSONArray("channels") ?: JSONArray()
            for (channelIndex in 0 until channels.length()) {
                val channel = channels.optJSONObject(channelIndex) ?: continue
                if (!channel.optBoolean("enabled", true)) continue
                val selected = (0 until channelIds.length()).any {
                    channelIds.optInt(it) == channel.optInt("id")
                }
                if (selected && channel.optString("type") != "local") {
                    NotificationSender.send(
                        channel,
                        rule.optString("name").ifBlank { instrument.optString("name") },
                        "${instrument.optString("name")} $observed"
                    )
                }
            }
        }
        store.writeState(state.toString())
        return Result.success()
    }

    private fun marketZone(market: String): ZoneId =
        if (market == "US") ZoneId.of("America/New_York") else ZoneId.of("Asia/Shanghai")

    private fun isMarketOpen(market: String, now: Instant): Boolean {
        val local = now.atZone(marketZone(market))
        if (local.dayOfWeek.value >= 6) return false
        val time = local.toLocalTime()
        return when (market) {
            "US" -> time >= LocalTime.of(9, 30) && time < LocalTime.of(16, 0)
            "HK" -> (time >= LocalTime.of(9, 30) && time < LocalTime.of(12, 0)) ||
                (time >= LocalTime.of(13, 0) && time < LocalTime.of(16, 0))
            else -> (time >= LocalTime.of(9, 30) && time < LocalTime.of(11, 30)) ||
                (time >= LocalTime.of(13, 0) && time < LocalTime.of(15, 0))
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
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        manager.notify((System.currentTimeMillis() and 0x7fffffff).toInt(), notification)
    }

    companion object {
        const val UNIQUE_NAME = "crazygame-alert-scan"
        private const val CHANNEL_ID = "crazygame_alerts"
    }
}

internal object AlertQuotes {
    fun fetch(instrument: JSONObject): JSONObject? {
        val symbol = instrument.optString("symbol")
        val market = instrument.optString("market")
        if (market == "FUND") return null
        val prefix = when {
            market == "HK" -> "hk"
            market == "US" -> "us"
            Regex("^[5689]").containsMatchIn(symbol) -> "sh"
            Regex("^[48]").containsMatchIn(symbol) -> "bj"
            else -> "sz"
        }
        val client = okhttp3.OkHttpClient()
        val request = okhttp3.Request.Builder()
            .url("https://qt.gtimg.cn/q=$prefix$symbol")
            .header("Referer", "https://gu.qq.com/")
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            val text = response.body!!.bytes().toString(Charsets.UTF_8)
            val value = text.substringAfter("=\"", "").substringBefore("\"")
            val parts = value.split("~")
            if (parts.size < 35) return null
            return JSONObject()
                .put("current_price", parts[3].toDoubleOrNull())
                .put("change_pct", parts[32].toDoubleOrNull())
        }
    }
}
