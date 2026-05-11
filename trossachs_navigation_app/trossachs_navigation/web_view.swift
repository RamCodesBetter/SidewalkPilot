import SwiftUI
import WebKit
import CoreLocation
import Combine

// MARK: - RouteInfo

struct RouteInfo {
    var summary: String
    var steps: [String]
    var distance: String
    var eta: String
}

// MARK: - WebBridge

final class WebBridge: NSObject, ObservableObject, WKScriptMessageHandler, CLLocationManagerDelegate {
    @Published var isReady = false
    @Published var routeInfo: RouteInfo?
    @Published var suggestions: [String] = []
    @Published var previewPlaying = false
    @Published var previewProgress: Double = 0
    @Published var previewStatus = ""

    weak var webView: WKWebView?
    private let locationManager = CLLocationManager()
    private var shouldCenterNextLocation = false

    override init() {
        super.init()
        locationManager.delegate = self
        locationManager.desiredAccuracy = kCLLocationAccuracyBest
    }

    // MARK: - JS → Swift messages

    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        DispatchQueue.main.async {
            switch message.name {
            case "ready":
                self.isReady = true
            case "routeResult":
                self.routeInfo = RouteInfo(
                    summary: body["summary"] as? String ?? "",
                    steps: body["steps"] as? [String] ?? [],
                    distance: body["distance"] as? String ?? "",
                    eta: body["eta"] as? String ?? ""
                )
            case "suggestions":
                self.suggestions = body["items"] as? [String] ?? []
            case "previewUpdate":
                self.previewProgress = (body["pct"] as? Double ?? 0) / 100.0
                self.previewStatus   = body["status"] as? String ?? ""
                self.previewPlaying  = body["playing"] as? Bool ?? false
            default: break
            }
        }
    }

    // MARK: - Location (CLLocationManager → inject into JS)

    func requestLocation(center: Bool = true) {
        shouldCenterNextLocation = center
        let status = locationManager.authorizationStatus
        if status == .notDetermined {
            locationManager.requestWhenInUseAuthorization()
        } else if status == .authorizedWhenInUse || status == .authorizedAlways {
            locationManager.startUpdatingLocation()
        } else {
            // Permission denied — show on map anyway via JS error path
            webView?.evaluateJavaScript("""
            summary.textContent = 'Location permission denied. Enable in Settings.';
            """)
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .authorizedWhenInUse ||
           manager.authorizationStatus == .authorizedAlways {
            manager.startUpdatingLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        let center = shouldCenterNextLocation
        shouldCenterNextLocation = false
        // Inject location directly into the page's JS state
        let js = """
        (function(){
            var fakePos = {
                coords: {
                    latitude: \(loc.coordinate.latitude),
                    longitude: \(loc.coordinate.longitude),
                    accuracy: \(loc.horizontalAccuracy)
                },
                timestamp: \(loc.timestamp.timeIntervalSince1970 * 1000)
            };
            updateCurrentLocation(fakePos, \(center ? "true" : "false") || (typeof followLocation !== 'undefined' && followLocation));
        })();
        """
        webView?.evaluateJavaScript(js)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: - Swift → JS actions

    func planRoute(start: String, goal: String) {
        let js = """
        document.getElementById('start').value = \(jsStr(start));
        document.getElementById('goal').value = \(jsStr(goal));
        planRoute();
        setTimeout(() => {
            const steps = Array.from(document.querySelectorAll('#directions li')).map(li => li.textContent);
            window.webkit.messageHandlers.routeResult.postMessage({
                summary: document.getElementById('summary').textContent,
                steps,
                distance: document.getElementById('distanceMetric').textContent,
                eta: document.getElementById('etaMetric').textContent
            });
        }, 500);
        """
        webView?.evaluateJavaScript(js)
    }

    func getSuggestions(query: String) {
        let js = """
        (function(){
            const q = \(jsStr(query.lowercased()));
            const pieces = q.split(' ').filter(Boolean);
            const found = addressIndex
                .filter(e => pieces.every(p => e.normalized.includes(p)))
                .sort((a,b) => scoreMatch(b,pieces)-scoreMatch(a,pieces))
                .slice(0,10).map(e => e.address+' ['+e.id+']');
            window.webkit.messageHandlers.suggestions.postMessage({items: found});
        })();
        """
        webView?.evaluateJavaScript(js)
    }

    func fitRoute()   { webView?.evaluateJavaScript("zoomToRoute(); requestDraw();") }
    func zoomIn()     { webView?.evaluateJavaScript("zoomAt(1.5,  canvas.clientWidth/2, canvas.clientHeight/2);") }
    func zoomOut()    { webView?.evaluateJavaScript("zoomAt(0.67, canvas.clientWidth/2, canvas.clientHeight/2);") }

    func clearRoute() {
        webView?.evaluateJavaScript("clearRoute();")
        DispatchQueue.main.async { self.routeInfo = nil; self.previewPlaying = false; self.previewProgress = 0; self.previewStatus = "" }
    }

    func setMap(_ key: String) {
        DispatchQueue.main.async {
            self.isReady = false
            self.routeInfo = nil
            self.suggestions = []
            self.previewPlaying = false
            self.previewProgress = 0
            self.previewStatus = ""
        }
        webView?.evaluateJavaScript("""
        (function(){
            if (window.setNavigationMap) {
                window.setNavigationMap(\(jsStr(key)));
                return;
            }
            var select = document.getElementById('mapSelect');
            if (select) select.value = \(jsStr(key));
            if (typeof init === 'function') init(\(jsStr(key)));
        })();
        """)
    }

    func startPreview()   { webView?.evaluateJavaScript("startPreview();") }
    func pausePreview()   { webView?.evaluateJavaScript("stopPreview(false);") }
    func restartPreview() { webView?.evaluateJavaScript("restartPreview();") }
    func setPreviewSpeed(_ s: Int) { webView?.evaluateJavaScript("document.getElementById('previewSpeed').value='\(s)'; ") }
    func setFollowPreview(_ on: Bool) { webView?.evaluateJavaScript("followCar = \(on ? "true" : "false");") }
    func setFollowLocation(_ on: Bool) { webView?.evaluateJavaScript("followLocation = \(on ? "true" : "false");") }

    private func jsStr(_ s: String) -> String {
        "'" + s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "'", with: "\\'") + "'"
    }
}

// MARK: - MapWebView

struct MapWebView: UIViewRepresentable {
    @ObservedObject var bridge: WebBridge

    func makeUIView(context: Context) -> WKWebView {
        let ucc = WKUserContentController()
        ["ready", "routeResult", "suggestions", "previewUpdate"].forEach { ucc.add(bridge, name: $0) }

        // Inject graph data before page scripts run
        let setup = """
        (function(){
            var s = document.createElement('style');
            s.textContent = `
                aside, header, .legend, .map-hud, .node-popup { display:none !important; }
                body,html{margin:0;padding:0;overflow:hidden;background:#e6edf4;}
                .app{display:block!important;height:100dvh!important;}
                main{display:block!important;height:100dvh!important;position:absolute;inset:0;}
                .map-wrap{position:absolute!important;inset:0!important;height:100dvh!important;}
                canvas{width:100%!important;height:100%!important;display:block;}
            `;
            document.head.appendChild(s);

            // Patch updatePreviewUi to post progress to Swift
            var _orig = window.updatePreviewUi;
            window.updatePreviewUi = function() {
                if(_orig) _orig();
                var total = routeDrawableLength();
                var pct = total ? Math.max(0, Math.min(100, preview.distance / total * 100)) : 0;
                window.webkit.messageHandlers.previewUpdate.postMessage({
                    pct: pct,
                    status: document.getElementById('previewStatus').textContent,
                    playing: preview.playing
                });
            };

            (function poll(){
                if(typeof indexReady !== 'undefined' && indexReady){
                    window.webkit.messageHandlers.ready.postMessage({});
                } else { setTimeout(poll, 300); }
            })();
        })();
        """
        ucc.addUserScript(WKUserScript(source: setup, injectionTime: .atDocumentEnd, forMainFrameOnly: true))

        let config = WKWebViewConfiguration()
        config.userContentController = ucc
        config.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")

        let wv = WKWebView(frame: .zero, configuration: config)
        wv.scrollView.isScrollEnabled = false
        wv.scrollView.bounces = false
        bridge.webView = wv

        if let url = Bundle.main.url(forResource: "trossachs_route_planner", withExtension: "html") {
            wv.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
