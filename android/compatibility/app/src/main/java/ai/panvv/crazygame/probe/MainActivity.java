package ai.panvv.crazygame.probe;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String HEALTH_URL = "http://127.0.0.1:8765/api/health";
    private static final int TEXT_COLOR = Color.rgb(235, 241, 255);
    private static final int BACKGROUND_COLOR = Color.rgb(7, 10, 18);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private TextView status;
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        status = new TextView(this);
        status.setTextColor(TEXT_COLOR);
        status.setTextSize(13);
        status.setPadding(28, 28, 28, 20);
        status.setText("Starting Python runtime...");

        webView = new WebView(this);
        webView.setBackgroundColor(BACKGROUND_COLOR);
        webView.getSettings().setJavaScriptEnabled(false);
        webView.setWebViewClient(new WebViewClient());

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(BACKGROUND_COLOR);
        layout.addView(
                status,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                )
        );
        layout.addView(
                webView,
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        0,
                        1
                )
        );
        setContentView(layout);

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        executor.execute(this::runProbe);
    }

    private void runProbe() {
        String result;
        try {
            result = Python.getInstance().getModule("probe").callAttr("run_self_check").toString();
        } catch (Exception error) {
            mainHandler.post(() -> status.setText("Python import failed:\n" + error));
            return;
        }

        mainHandler.post(() -> status.setText(result));
        if (!result.contains("\"ok\": true")) {
            return;
        }

        new Thread(() -> {
            try {
                Python.getInstance().getModule("probe").callAttr("start_server");
            } catch (Exception error) {
                mainHandler.post(() -> status.append("\nServer failed:\n" + error));
            }
        }, "crazygame-python-server").start();

        waitForServer(40);
    }

    private void waitForServer(int attemptsRemaining) {
        if (attemptsRemaining <= 0) {
            mainHandler.post(() -> status.append("\nLocal server did not become ready."));
            return;
        }
        executor.execute(() -> {
            try {
                HttpURLConnection connection = (HttpURLConnection) new URL(HEALTH_URL).openConnection();
                connection.setConnectTimeout(500);
                connection.setReadTimeout(500);
                if (connection.getResponseCode() == 200) {
                    mainHandler.post(() -> webView.loadUrl(HEALTH_URL));
                    return;
                }
            } catch (Exception ignored) {
                // Poll until the configured attempt limit.
            }
            try {
                Thread.sleep(250);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            waitForServer(attemptsRemaining - 1);
        });
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        webView.destroy();
        super.onDestroy();
    }
}
