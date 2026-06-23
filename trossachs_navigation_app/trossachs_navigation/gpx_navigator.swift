import Foundation
import CoreLocation
import AVFoundation
import Combine

// MARK: - GPX parsing

enum GPX {
    /// Parse a GPX file's coordinates. Prefers track points, then route points,
    /// then waypoints (trkpt > rtept > wpt) — all carry lat/lon attributes.
    static func coordinates(from data: Data) -> [CLLocationCoordinate2D] {
        let collector = GPXCollector()
        let parser = XMLParser(data: data)
        parser.delegate = collector
        parser.parse()
        if !collector.trkpts.isEmpty { return collector.trkpts }
        if !collector.rtepts.isEmpty { return collector.rtepts }
        return collector.wpts
    }
}

private final class GPXCollector: NSObject, XMLParserDelegate {
    var trkpts: [CLLocationCoordinate2D] = []
    var rtepts: [CLLocationCoordinate2D] = []
    var wpts: [CLLocationCoordinate2D] = []

    func parser(_ parser: XMLParser, didStartElement elementName: String,
                namespaceURI: String?, qualifiedName qName: String?,
                attributes attributeDict: [String: String] = [:]) {
        guard let latS = attributeDict["lat"], let lonS = attributeDict["lon"],
              let lat = Double(latS), let lon = Double(lonS) else { return }
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        switch elementName {
        case "trkpt": trkpts.append(coord)
        case "rtept": rtepts.append(coord)
        case "wpt":   wpts.append(coord)
        default: break
        }
    }
}

// MARK: - Maneuver

struct GPXManeuver: Identifiable {
    let id = UUID()
    let coordinate: CLLocationCoordinate2D
    let instruction: String
    let distanceFromStart: CLLocationDistance
}

// MARK: - Navigator (turn-by-turn + voice)

final class GPXNavigator: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var isNavigating = false
    @Published var routeName = ""
    @Published var currentInstruction = ""
    @Published var distanceToNext: CLLocationDistance = 0
    @Published var remainingDistance: CLLocationDistance = 0
    @Published var lastError: String?

    private var maneuvers: [GPXManeuver] = []
    private var totalDistance: CLLocationDistance = 0
    private var nextIndex = 0
    private var preparedIndex = -1

    private let manager = CLLocationManager()
    private let synth = AVSpeechSynthesizer()

    // Tunables
    private let turnThresholdDeg = 30.0   // bearing change that counts as a turn
    private let prepareDistanceM = 30.0   // "in X meters, ..."
    private let arriveDistanceM  = 12.0   // maneuver considered reached
    private let minSegmentM      = 6.0    // drop GPS-noise points closer than this

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.activityType = .fitness
    }

    // MARK: Load + start / stop

    func loadAndStart(url: URL, name: String) {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else {
            lastError = "Could not read GPX file."; return
        }
        let clean = Self.simplify(GPX.coordinates(from: data), minSegmentM: minSegmentM)
        guard clean.count >= 2 else {
            lastError = "GPX has too few points to navigate."; return
        }
        maneuvers = Self.buildManeuvers(clean, turnThresholdDeg: turnThresholdDeg)
        totalDistance = maneuvers.last?.distanceFromStart ?? 0
        routeName = name
        nextIndex = 0
        preparedIndex = -1
        remainingDistance = totalDistance
        currentInstruction = maneuvers.first?.instruction ?? "Navigating"
        lastError = nil
        isNavigating = true
        configureAudioSession()
        requestAndStart()
        announce("Starting navigation. \(max(0, maneuvers.count - 1)) steps, \(Self.formatDistance(totalDistance)) total.")
    }

    func stop() {
        isNavigating = false
        manager.stopUpdatingLocation()
        synth.stopSpeaking(at: .immediate)
        currentInstruction = ""
        deactivateAudioSession()
    }

    func repeatInstruction() {
        guard isNavigating, nextIndex < maneuvers.count else { return }
        announce(maneuvers[nextIndex].instruction)
    }

    // MARK: Location following

    private func requestAndStart() {
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways: manager.startUpdatingLocation()
        default: lastError = "Location permission is needed for turn-by-turn."
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard isNavigating else { return }
        if manager.authorizationStatus == .authorizedWhenInUse ||
           manager.authorizationStatus == .authorizedAlways {
            manager.startUpdatingLocation()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard isNavigating, let here = locations.last, nextIndex < maneuvers.count else { return }
        let target = maneuvers[nextIndex]
        let targetLoc = CLLocation(latitude: target.coordinate.latitude, longitude: target.coordinate.longitude)
        let d = here.distance(from: targetLoc)
        distanceToNext = d
        remainingDistance = max(0, totalDistance - target.distanceFromStart) + d

        // Pre-announce once as we approach.
        if d <= prepareDistanceM && d > arriveDistanceM && preparedIndex != nextIndex {
            preparedIndex = nextIndex
            currentInstruction = target.instruction
            announce("In \(Self.formatDistance(d)), \(target.instruction.lowercased())")
        }
        // Reached the maneuver -> announce + advance.
        if d <= arriveDistanceM {
            currentInstruction = target.instruction
            announce(target.instruction)
            nextIndex += 1
            if nextIndex >= maneuvers.count {
                announce("You have arrived.")
                stop()
            }
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: Voice

    private func announce(_ text: String) {
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: "en-US")
        u.rate = AVSpeechUtteranceDefaultSpeechRate
        synth.speak(u)
    }

    private func configureAudioSession() {
        let session = AVAudioSession.sharedInstance()
        // .playback + .voicePrompt routes to AirPods/speaker and ducks music.
        try? session.setCategory(.playback, mode: .voicePrompt, options: [.duckOthers])
        try? session.setActive(true)
    }

    private func deactivateAudioSession() {
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    // MARK: Geometry (pure, testable)

    static func simplify(_ coords: [CLLocationCoordinate2D], minSegmentM: Double) -> [CLLocationCoordinate2D] {
        guard let first = coords.first else { return [] }
        var out = [first]
        for c in coords.dropFirst() {
            let last = out[out.count - 1]
            let d = CLLocation(latitude: last.latitude, longitude: last.longitude)
                .distance(from: CLLocation(latitude: c.latitude, longitude: c.longitude))
            if d >= minSegmentM { out.append(c) }
        }
        return out
    }

    static func buildManeuvers(_ pts: [CLLocationCoordinate2D], turnThresholdDeg: Double) -> [GPXManeuver] {
        guard pts.count >= 2 else { return [] }
        var dists = [CLLocationDistance](repeating: 0, count: pts.count)
        var cumulative: CLLocationDistance = 0
        for i in 1..<pts.count {
            cumulative += CLLocation(latitude: pts[i-1].latitude, longitude: pts[i-1].longitude)
                .distance(from: CLLocation(latitude: pts[i].latitude, longitude: pts[i].longitude))
            dists[i] = cumulative
        }
        var maneuvers: [GPXManeuver] = [
            GPXManeuver(coordinate: pts[0], instruction: "Head out along the route", distanceFromStart: 0)
        ]
        if pts.count >= 3 {
            for i in 1..<(pts.count - 1) {
                let turn = signedAngle(bearing(pts[i-1], pts[i]), bearing(pts[i], pts[i+1]))
                if abs(turn) >= turnThresholdDeg {
                    maneuvers.append(GPXManeuver(coordinate: pts[i],
                                                 instruction: turnInstruction(turn),
                                                 distanceFromStart: dists[i]))
                }
            }
        }
        maneuvers.append(GPXManeuver(coordinate: pts[pts.count - 1],
                                     instruction: "Arrive at destination",
                                     distanceFromStart: cumulative))
        return maneuvers
    }

    static func bearing(_ a: CLLocationCoordinate2D, _ b: CLLocationCoordinate2D) -> Double {
        let lat1 = a.latitude * .pi / 180, lat2 = b.latitude * .pi / 180
        let dLon = (b.longitude - a.longitude) * .pi / 180
        let y = sin(dLon) * cos(lat2)
        let x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon)
        return (atan2(y, x) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
    }

    /// Signed turn from bearing `from` to `to`: positive = right, negative = left, range (-180, 180].
    static func signedAngle(_ from: Double, _ to: Double) -> Double {
        (to - from + 540).truncatingRemainder(dividingBy: 360) - 180
    }

    static func turnInstruction(_ turn: Double) -> String {
        let mag = abs(turn)
        let dir = turn > 0 ? "right" : "left"
        if mag >= 110 { return "Make a sharp \(dir)" }
        if mag >= 45  { return "Turn \(dir)" }
        return "Bear \(dir)"
    }

    static func formatDistance(_ m: CLLocationDistance) -> String {
        m >= 1000 ? String(format: "%.1f km", m / 1000) : "\(Int(m.rounded())) meters"
    }
}
