import SwiftUI
import MapKit
import CoreLocation

// MARK: - Native MapKit nav map (kept fully separate from the HTML planner map)

/// A follow-the-user MKMapView that draws the active route polyline and a
/// destination pin. Camera follows with heading until the user pans, then the
/// caller shows a Re-center button that flips `follow` back on.
struct NavMapView: UIViewRepresentable {
    var routeCoordinates: [CLLocationCoordinate2D]
    @Binding var follow: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.showsUserLocation = true
        map.showsCompass = true
        map.pointOfInterestFilter = .excludingAll
        map.setUserTrackingMode(.followWithHeading, animated: false)
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        // Re-draw the polyline + destination pin only when the route changes.
        if context.coordinator.drawnCount != routeCoordinates.count {
            context.coordinator.drawnCount = routeCoordinates.count
            map.removeOverlays(map.overlays)
            map.removeAnnotations(map.annotations.filter { !($0 is MKUserLocation) })
            if routeCoordinates.count >= 2 {
                let line = MKPolyline(coordinates: routeCoordinates, count: routeCoordinates.count)
                map.addOverlay(line)
                if let dest = routeCoordinates.last {
                    let pin = MKPointAnnotation()
                    pin.coordinate = dest
                    pin.title = "Destination"
                    map.addAnnotation(pin)
                }
            }
        }

        // Apply follow state without fighting the user's manual pans.
        let desired: MKUserTrackingMode = follow ? .followWithHeading : .none
        if map.userTrackingMode != desired && !context.coordinator.suppressTrackingWrite {
            map.setUserTrackingMode(desired, animated: true)
        }
    }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var parent: NavMapView
        var drawnCount = -1
        var suppressTrackingWrite = false

        init(_ parent: NavMapView) { self.parent = parent }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            guard let line = overlay as? MKPolyline else { return MKOverlayRenderer(overlay: overlay) }
            let r = MKPolylineRenderer(polyline: line)
            r.strokeColor = UIColor(red: 0.05, green: 0.47, blue: 0.95, alpha: 0.95)
            r.lineWidth = 7
            r.lineCap = .round
            r.lineJoin = .round
            return r
        }

        // When the user drags the map, MapKit drops tracking to .none — reflect
        // that in `follow` so the Re-center button appears.
        func mapView(_ mapView: MKMapView, didChange mode: MKUserTrackingMode, animated: Bool) {
            let following = mode != .none
            if parent.follow != following {
                suppressTrackingWrite = true
                DispatchQueue.main.async {
                    self.parent.follow = following
                    self.suppressTrackingWrite = false
                }
            }
        }
    }
}

// MARK: - Full-screen navigation mode UI

struct NavigationModeView: View {
    @ObservedObject var nav: GPXNavigator
    var onEnd: () -> Void

    @State private var follow = true
    private let accent = Color(red: 0.05, green: 0.47, blue: 0.95)

    var body: some View {
        ZStack {
            NavMapView(routeCoordinates: nav.routeCoordinates, follow: $follow)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                maneuverBanner
                Spacer()
                if !follow { recenterButton }
                etaBar
            }
        }
    }

    // Top: turn arrow + instruction + distance-to-next (the Google card).
    private var maneuverBanner: some View {
        HStack(spacing: 14) {
            Image(systemName: Self.maneuverIcon(nav.currentInstruction))
                .font(.system(size: 30, weight: .bold))
                .foregroundColor(.white)
                .frame(width: 46)
            VStack(alignment: .leading, spacing: 2) {
                if nav.distanceToNext > 0 {
                    Text("In \(GPXNavigator.formatDistance(nav.distanceToNext))")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.white.opacity(0.85))
                }
                Text(nav.currentInstruction.isEmpty ? "Navigating" : nav.currentInstruction)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
            }
            Spacer()
            Button { nav.repeatInstruction() } label: {
                Image(systemName: "speaker.wave.2.fill")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.white.opacity(0.9))
                    .frame(width: 40, height: 40)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(accent)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .shadow(color: .black.opacity(0.25), radius: 12, x: 0, y: 6)
        .padding(.horizontal, 10)
        .padding(.top, 6)
    }

    private var recenterButton: some View {
        Button { follow = true } label: {
            Label("Re-center", systemImage: "location.fill")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(accent)
                .padding(.horizontal, 16).padding(.vertical, 11)
                .background(.regularMaterial, in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.5), lineWidth: 1))
                .shadow(color: .black.opacity(0.18), radius: 8, x: 0, y: 3)
        }
        .padding(.bottom, 12)
    }

    // Bottom: arrival time · time left · distance left · End.
    private var etaBar: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text(Self.arrivalText(nav.remainingTime))
                    .font(.system(size: 20, weight: .bold))
                    .foregroundColor(.primary)
                HStack(spacing: 8) {
                    Text(GPXNavigator.formatDuration(nav.remainingTime))
                    Text("·")
                    Text(GPXNavigator.formatDistance(nav.remainingDistance))
                }
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(.secondary)
            }
            Spacer()
            Button(action: onEnd) {
                Text("End")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 78, height: 48)
                    .background(Color.red)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.2), radius: 18, x: 0, y: -4)
        )
        .padding(.horizontal, 8)
        .padding(.bottom, 6)
    }

    // MARK: - Formatting helpers

    /// Clock time of arrival, 12-hour with am/pm (e.g. "3:42 PM").
    static func arrivalText(_ remaining: TimeInterval) -> String {
        let arrival = Date().addingTimeInterval(remaining)
        let f = DateFormatter()
        f.dateFormat = "h:mm a"
        return f.string(from: arrival)
    }

    /// Map a turn instruction to an SF Symbol arrow.
    static func maneuverIcon(_ instruction: String) -> String {
        let s = instruction.lowercased()
        if s.contains("arrive") || s.contains("destination") { return "mappin.circle.fill" }
        if s.contains("sharp") && s.contains("left")  { return "arrow.turn.up.left" }
        if s.contains("sharp") && s.contains("right") { return "arrow.turn.up.right" }
        if s.contains("left")  { return "arrow.turn.up.left" }
        if s.contains("right") { return "arrow.turn.up.right" }
        return "location.north.line.fill"
    }
}
