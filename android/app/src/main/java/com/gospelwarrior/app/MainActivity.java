package com.gospelwarrior.app;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import java.io.IOException;
import java.io.InputStream;
import java.io.ByteArrayInputStream;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Native Android shell for the offline Gospel Warrior study companion.
 *
 * The website is served from the APK through a stable local HTTPS origin so
 * fetch(), localStorage, and IndexedDB behave like they do in a normal web
 * app while the full library remains available without a connection.
 */
public final class MainActivity extends Activity {
    private static final String APP_HOST = "gospel-warrior.local";
    private static final String APP_SCHEME = "https";
    private static final String ASSET_ROOT = "website/";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.setStatusBarColor(Color.rgb(32, 56, 46));
        window.setNavigationBarColor(Color.rgb(22, 41, 31));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            window.getDecorView().setSystemUiVisibility(0);
        }

        webView = new WebView(this);
        configureWebView(webView);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(32, 56, 46));
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            root.setOnApplyWindowInsetsListener((v, insets) -> {
                Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            });
        }
        setContentView(root);
        String url = savedInstanceState == null ? null : savedInstanceState.getString("readingUrl");
        webView.loadUrl(url != null && isLocal(Uri.parse(url)) ? url : APP_SCHEME + "://" + APP_HOST + "/study.html");
    }

    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setTextZoom(100);

        view.setBackgroundColor(Color.rgb(244, 238, 220));
        view.setOverScrollMode(View.OVER_SCROLL_NEVER);
        view.setWebViewClient(new LocalContentClient());
        view.setWebChromeClient(new WebChromeClient());
        view.addJavascriptInterface(new ClipboardBridge(), "GospelAndroid");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            view.getSettings().setSafeBrowsingEnabled(true);
        }
    }

    private final class LocalContentClient extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            return localResponse(request.getUrl());
        }

        @SuppressWarnings("deprecation")
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
            return localResponse(Uri.parse(url));
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if (isLocal(uri)) return false;
            openExternal(uri);
            return true;
        }

        @SuppressWarnings("deprecation")
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            Uri uri = Uri.parse(url);
            if (isLocal(uri)) return false;
            openExternal(uri);
            return true;
        }
    }

    private WebResourceResponse localResponse(Uri uri) {
        if (!isLocal(uri)) return null;
        String path = uri.getPath();
        if (path == null || path.isEmpty() || "/".equals(path)) path = "/study.html";
        if (path.contains("..") || path.startsWith("//")) return missingResponse();
        String assetPath = ASSET_ROOT + path.substring(1);
        boolean packagedGzipAsJson = false;
        try {
            InputStream stream;
            try {
                stream = getAssets().open(assetPath);
            } catch (IOException gzipNameRemovedByAapt) {
                if (!path.endsWith(".gz")) return missingResponse();
                assetPath = ASSET_ROOT + path.substring(1, path.length() - 3);
                stream = getAssets().open(assetPath);
                packagedGzipAsJson = true;
            }
            String mime = mimeType(path);
            Map<String, String> headers = new HashMap<>();
            headers.put("Cache-Control", path.endsWith(".gz") ? "public, max-age=3600" : "no-cache");
            headers.put("Access-Control-Allow-Origin", "*");
            if (packagedGzipAsJson) headers.put("X-Gospel-Warrior-Plain-Json", "true");
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                return new WebResourceResponse(mime, null, 200, "OK", headers, stream);
            }
            return new WebResourceResponse(mime, null, stream);
        } catch (IOException ignored) {
            return missingResponse();
        }
    }

    private WebResourceResponse missingResponse() {
        return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found",
            new HashMap<>(), new ByteArrayInputStream(new byte[0]));
    }

    public final class ClipboardBridge {
        @JavascriptInterface
        public void copyText(String text) {
            if (text == null) return;
            runOnUiThread(() -> {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                clipboard.setPrimaryClip(ClipData.newPlainText("Gospel Warrior study", text));
            });
        }
    }

    private boolean isLocal(Uri uri) {
        return uri != null && APP_SCHEME.equalsIgnoreCase(uri.getScheme()) && APP_HOST.equalsIgnoreCase(uri.getHost());
    }

    private String mimeType(String path) {
        String lower = path.toLowerCase(Locale.US);
        if (lower.endsWith(".html")) return "text/html";
        if (lower.endsWith(".css")) return "text/css";
        if (lower.endsWith(".js")) return "text/javascript";
        if (lower.endsWith(".json")) return "application/json";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".webp")) return "image/webp";
        if (lower.endsWith(".gz")) return "application/gzip";
        if (lower.endsWith(".txt")) return "text/plain";
        return "application/octet-stream";
    }

    private void openExternal(Uri uri) {
        if (uri == null || uri.getScheme() == null) return;
        String scheme = uri.getScheme().toLowerCase(Locale.US);
        if (!"http".equals(scheme) && !"https".equals(scheme) && !"mailto".equals(scheme)) return;
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException ignored) {
            // Keep the study reader usable when no external handler exists.
        }
    }

    @Override
    public void onBackPressed() {
        if (webView == null) { super.onBackPressed(); return; }
        webView.evaluateJavascript("window.gospelAndroidBack ? window.gospelAndroidBack() : false", handled -> {
            if ("true".equals(handled)) return;
            if (webView.canGoBack()) webView.goBack(); else finish();
        });
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        if (webView != null) state.putString("readingUrl", webView.getUrl());
        super.onSaveInstanceState(state);
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.evaluateJavascript("typeof saveReadingPosition === 'function' && saveReadingPosition()", null);
            webView.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
