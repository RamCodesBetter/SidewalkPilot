import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var bridge = WebBridge()
    private let accent = Color(red: 0.02, green: 0.47, blue: 0.82)
    private let success = Color(red: 0.08, green: 0.62, blue: 0.35)

    // Search state
    @State private var selectedMap: NavMap = .trossachs
    @State private var startText = "HOME"
    @State private var goalText = ""
    @State private var activeField: Field? = nil
    @State private var keyboardHeight: CGFloat = 0

    // Sheet state
    @State private var sheetHeight: CGFloat = 160
    private let peekH: CGFloat = 160
    private let halfH: CGFloat = 320
    private let fullH: CGFloat = 620
    @State private var activeTab: Tab = .route

    // Preview state
    @State private var followPreview = true
    @State private var previewSpeed = 16

    // GPX turn-by-turn (voice) navigation
    @StateObject private var gpxNav = GPXNavigator()
    @State private var showGPXImporter = false

    enum Field: Hashable { case start, goal }
    enum Tab: String, CaseIterable { case route = "Route", steps = "Steps", preview = "Preview" }
    enum NavMap: String, CaseIterable, Identifiable {
        case trossachs
        case sammamish
        case issaquah

        var id: String { rawValue }
        var title: String {
            switch self {
            case .trossachs: return "Trossachs"
            case .sammamish: return "Sammamish"
            case .issaquah: return "Issaquah"
            }
        }
        var defaultStart: String {
            self == .issaquah ? "" : "HOME"
        }
    }

    var body: some View {
        GeometryReader { proxy in
            let safeTop = proxy.safeAreaInsets.top
            let safeBottom = proxy.safeAreaInsets.bottom

            ZStack(alignment: .bottom) {
                // ── MAP ──────────────────────────────────────────────────────
                MapWebView(bridge: bridge)
                    .ignoresSafeArea()
                    .onTapGesture { dismissKeyboard() }
                    .fileImporter(isPresented: $showGPXImporter,
                                  allowedContentTypes: [UTType(filenameExtension: "gpx") ?? .xml, .xml, .item],
                                  allowsMultipleSelection: false,
                                  onCompletion: handleGPXImport)

                topMapBadge(safeTop: safeTop)
                gpxNavOverlay(safeTop: safeTop)

                // ── LOADING OVERLAY ──────────────────────────────────────────
                if !bridge.isReady {
                    ZStack {
                        Color(.systemBackground).ignoresSafeArea()
                        VStack(spacing: 16) {
                            ProgressView()
                                .scaleEffect(1.4)
                            Text("Loading \(selectedMap.title) Navigation...")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                    .transition(.opacity)
                    .zIndex(10)
                }

                // ── ZOOM BUTTONS ─────────────────────────────────────────────
                VStack(spacing: 8) {
                    // Locate me
                    Button { bridge.requestLocation() } label: {
                        Image(systemName: "location.fill")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundColor(accent)
                            .frame(width: 48, height: 48)
                            .background(.ultraThinMaterial)
                            .clipShape(Circle())
                            .overlay(Circle().stroke(.white.opacity(0.55), lineWidth: 1))
                            .shadow(color: .black.opacity(0.18), radius: 10, x: 0, y: 4)
                    }

                    // Zoom
                    VStack(spacing: 0) {
                        zoomButton(icon: "plus")  { bridge.zoomIn() }
                        Divider().frame(width: 44)
                        zoomButton(icon: "minus") { bridge.zoomOut() }
                    }
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(.white.opacity(0.55), lineWidth: 1))
                    .shadow(color: .black.opacity(0.18), radius: 10, x: 0, y: 4)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
                .padding(.trailing, 14)
                .padding(.bottom, sheetHeight + max(16, safeBottom))

                // ── BOTTOM SHEET ─────────────────────────────────────────────
                bottomSheet

                // ── SUGGESTION OVERLAY (outside sheet so sheet doesn't resize) ──
                if !bridge.suggestions.isEmpty {
                    suggestionOverlay(safeTop: safeTop, availableHeight: proxy.size.height)
                        .zIndex(200)
                }
            }
            .ignoresSafeArea(edges: .bottom)
        }
        .animation(.easeOut(duration: 0.4), value: bridge.isReady)
        .onChange(of: bridge.isReady) { _, ready in
            if ready {
                bridge.setFollowPreview(true)
                bridge.requestLocation(center: true)
            }
        }
        .onChange(of: selectedMap) { _, map in
            switchMap(map)
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillShowNotification)) { n in
            let frame = (n.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect) ?? .zero
            withAnimation(.easeOut(duration: 0.25)) {
                keyboardHeight = frame.height
                sheetHeight = max(sheetHeight, frame.height + 220)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            withAnimation(.easeOut(duration: 0.25)) { keyboardHeight = 0 }
        }
        // Full-screen native turn-by-turn (MapKit) whenever the navigator runs.
        // Kept separate from the HTML planner map.
        .fullScreenCover(isPresented: Binding(
            get: { gpxNav.isNavigating },
            set: { if !$0 { gpxNav.stop() } }
        )) {
            NavigationModeView(nav: gpxNav, onEnd: { gpxNav.stop() })
        }
    }

    // MARK: - Bottom sheet

    private func topMapBadge(safeTop: CGFloat) -> some View {
        HStack(spacing: 10) {
            ZStack {
                Circle().fill(accent)
                Image(systemName: "car.fill")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(.white)
            }
            .frame(width: 30, height: 30)

            VStack(alignment: .leading, spacing: 1) {
                Text(selectedMap.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.primary)
                Text(bridge.isReady ? "Sidewalk navigation ready" : "Loading map data")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(.white.opacity(0.55), lineWidth: 1))
        .shadow(color: .black.opacity(0.14), radius: 12, x: 0, y: 5)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .padding(.top, safeTop + 112)
        .padding(.leading, 14)
        .padding(.trailing, 14)
        .opacity(activeField == nil ? 1 : 0)
        .animation(.easeOut(duration: 0.18), value: activeField)
    }

    private var bottomSheet: some View {
        VStack(spacing: 0) {
            // Drag handle
            Capsule()
                .fill(Color(.systemGray4))
                .frame(width: 36, height: 5)
                .padding(.top, 10)
                .padding(.bottom, 6)

            sheetTitle
                .padding(.horizontal, 16)
                .padding(.bottom, 8)

            mapPicker
                .padding(.horizontal, 16)
                .padding(.bottom, bridge.routeInfo == nil ? 12 : 8)

            // Tab bar (only when route exists)
            if bridge.routeInfo != nil {
                tabBar
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)
            }

            // Content
            if activeTab == .steps {
                stepsTab
            } else if activeTab == .preview {
                previewTab
            } else {
                routeTab
            }

            Spacer(minLength: 0)
        }
        .frame(height: sheetHeight)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(.regularMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(Color(.systemBackground).opacity(0.82))
                )
                .shadow(color: .black.opacity(0.20), radius: 22, x: 0, y: -6)
        )
        .gesture(dragGesture)
        .animation(.spring(response: 0.32, dampingFraction: 0.78), value: sheetHeight)
    }

    private var sheetTitle: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Route Planner")
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(.primary)
                Text(bridge.routeInfo == nil ? "Enter an address or node ID" : "Sidewalk route active")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            if bridge.routeInfo != nil {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundColor(success)
                    .font(.system(size: 22, weight: .semibold))
            }
        }
    }

    private var mapPicker: some View {
        Picker("Map", selection: $selectedMap) {
            ForEach(NavMap.allCases) { map in
                Text(map.title).tag(map)
            }
        }
        .pickerStyle(.segmented)
    }

    private var tabBar: some View {
        HStack(spacing: 4) {
            ForEach(Tab.allCases, id: \.self) { tab in
                Button {
                    activeTab = tab
                    withAnimation { sheetHeight = tab == .steps ? fullH : halfH }
                } label: {
                    Text(tab.rawValue)
                        .font(.system(size: 14, weight: activeTab == tab ? .semibold : .medium))
                        .foregroundColor(activeTab == tab ? .white : .secondary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 34)
                        .background(activeTab == tab ? accent : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(4)
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    // Route tab: search + action buttons + summary
    private var routeTab: some View {
        VStack(spacing: 0) {
            searchFields
                .padding(.horizontal, 16)

            actionRow
                .padding(.horizontal, 16)
                .padding(.top, 10)

            if let info = bridge.routeInfo {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(info.summary)
                            .font(.system(size: 15, weight: .semibold))
                            .lineLimit(2)
                        HStack(spacing: 12) {
                            Label(info.distance, systemImage: "ruler")
                            Label(info.eta, systemImage: "clock")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                    Spacer()
                    Button {
                        bridge.fitRoute()
                    } label: {
                        Image(systemName: "arrow.up.left.and.arrow.down.right")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundColor(accent)
                            .frame(width: 40, height: 40)
                            .background(Color(.systemGray6))
                            .clipShape(Circle())
                    }
                }
                .padding(14)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                .padding(.horizontal, 16)
                .padding(.top, 14)
            } else if !bridge.isReady {
                loadingRow
            }
        }
    }

    // Steps tab: full directions list
    private var stepsTab: some View {
        Group {
            if let info = bridge.routeInfo, !info.steps.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(info.steps.enumerated()), id: \.offset) { i, step in
                            HStack(alignment: .top, spacing: 14) {
                                ZStack {
                                    Circle()
                                        .fill(i == 0 ? success : i == info.steps.count-1 ? Color.red : Color(.systemGray5))
                                        .frame(width: 30, height: 30)
                                    if i == 0 {
                                        Image(systemName: "location.fill").font(.system(size: 11)).foregroundColor(.white)
                                    } else if i == info.steps.count-1 {
                                        Image(systemName: "mappin").font(.system(size: 11)).foregroundColor(.white)
                                    } else {
                                        Text("\(i)").font(.caption2.weight(.bold)).foregroundColor(.primary)
                                    }
                                }
                                Text(step)
                                    .font(.system(size: 15, weight: i == 0 || i == info.steps.count-1 ? .semibold : .regular))
                                    .foregroundColor(.primary)
                                    .padding(.vertical, 14)
                                Spacer()
                            }
                            .padding(.horizontal, 16)
                            if i < info.steps.count - 1 {
                                Divider().padding(.leading, 58)
                            }
                        }
                    }
                    .padding(.bottom, 40)
                }
            } else {
                Text("Plan a route to see steps.")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(16)
            }
        }
    }

    // MARK: - Search fields (Google Maps style)

    private var searchFields: some View {
        HStack(spacing: 10) {
            // Dot indicators
            VStack(spacing: 4) {
                Circle().fill(success).frame(width: 9, height: 9)
                VStack(spacing: 2) {
                    ForEach(0..<3) { _ in
                        Circle().fill(Color(.systemGray4)).frame(width: 3, height: 3)
                    }
                }
                Circle().fill(Color.red).frame(width: 9, height: 9)
            }

            VStack(spacing: 8) {
                searchInput(placeholder: "Start", text: $startText, field: .start)
                searchInput(placeholder: "Destination", text: $goalText, field: .goal)
            }
        }
    }

    private func searchInput(placeholder: String, text: Binding<String>, field: Field) -> some View {
        HStack(spacing: 8) {
            Image(systemName: field == .start ? "location.circle.fill" : "mappin.circle.fill")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(field == .start ? success : .red)
            StableTextField(
                placeholder: placeholder,
                text: text,
                keepFocus: !bridge.suggestions.isEmpty,
                onCommit: { planRoute() },
                onChange: { q in
                    activeField = field
                    if q.count > 1 {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                            if text.wrappedValue == q { bridge.getSuggestions(query: q) }
                        }
                    } else {
                        bridge.suggestions = []
                    }
                }
            )
        }
        .frame(height: 44)
        .padding(.horizontal, 12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(activeField == field ? accent.opacity(0.45) : Color.clear, lineWidth: 1.5)
        )
    }

    // MARK: - Suggestion overlay (floats above sheet, doesn't resize it)

    private func suggestionOverlay(safeTop: CGFloat, availableHeight: CGFloat) -> some View {
        let maxPopupHeight = max(120, min(280, availableHeight - sheetHeight - safeTop - 34))

        return ScrollView {
            VStack(spacing: 0) {
                ForEach(bridge.suggestions.prefix(6), id: \.self) { s in
                    HStack(spacing: 12) {
                        Image(systemName: "mappin.circle.fill")
                            .foregroundColor(.red).font(.system(size: 16))
                        Text(s.components(separatedBy: " [").first ?? s)
                            .font(.subheadline).foregroundColor(.primary)
                            .lineLimit(2)
                            .minimumScaleFactor(0.88)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .contentShape(Rectangle())
                    .simultaneousGesture(TapGesture().onEnded {
                        let address = s.components(separatedBy: " [").first ?? s
                        if activeField == .start { startText = address }
                        else { goalText = address }
                        activeField = nil
                        bridge.suggestions = []  // clears keepFocus first
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                        }
                        planRoute()
                    })
                    if s != bridge.suggestions.prefix(6).last { Divider().padding(.leading, 44) }
                }
            }
        }
        .scrollIndicators(.hidden)
        .frame(maxHeight: maxPopupHeight)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(.white.opacity(0.5), lineWidth: 1))
        .shadow(color: .black.opacity(0.18), radius: 16, x: 0, y: -5)
        .padding(.horizontal, 12)
        .padding(.bottom, sheetHeight)
        .padding(.top, safeTop + 12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
    }

    // MARK: - Suggestions (kept for reference, no longer used in sheet)

    private var suggestionList: some View {
        ScrollView {
            VStack(spacing: 0) {
                ForEach(bridge.suggestions, id: \.self) { s in
                    Text(s)
                        .font(.subheadline)
                        .foregroundColor(.primary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 11)
                        .padding(.horizontal, 4)
                        .contentShape(Rectangle())
                        // Use simultaneousGesture so UITextField keeps first responder
                        .simultaneousGesture(TapGesture().onEnded {
                            let address = s.components(separatedBy: " [").first ?? s
                            if activeField == .start { startText = address }
                            else { goalText = address }
                            bridge.suggestions = []
                            activeField = nil
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                            planRoute()
                        })
                    Divider()
                }
            }
        }
        .frame(maxHeight: 260)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.1), radius: 6, x: 0, y: 3)
    }

    // MARK: - Action row

    private var actionRow: some View {
        HStack(spacing: 10) {
            Button(action: planRoute) {
                Label("Route", systemImage: "arrow.triangle.turn.up.right.diamond.fill")
                    .font(.system(size: 15, weight: .semibold))
                    .frame(maxWidth: .infinity)
                    .frame(height: 46)
                    .background(bridge.isReady ? accent : Color(.systemGray4))
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .disabled(!bridge.isReady)

            Button {
                swap(&startText, &goalText)
                planRoute()
            } label: {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(accent)
                        .frame(width: 46, height: 46)
                        .background(Color(.systemGray6))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }

            if bridge.routeInfo != nil {
                Button {
                    bridge.clearRoute()
                    withAnimation { sheetHeight = peekH }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.secondary)
                        .frame(width: 46, height: 46)
                        .background(Color(.systemGray6))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
        }
    }

    // MARK: - Preview tab

    private var previewTab: some View {
        VStack(spacing: 16) {
            if bridge.routeInfo == nil {
                Text("Plan a route first to use preview.")
                    .font(.subheadline).foregroundColor(.secondary).padding(16)
            } else {
                // Progress bar
                VStack(alignment: .leading, spacing: 6) {
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Color(.systemGray5)).frame(height: 8)
                            Capsule().fill(accent)
                                .frame(width: max(0, geo.size.width * bridge.previewProgress), height: 8)
                                .animation(.linear(duration: 0.4), value: bridge.previewProgress)
                        }
                    }
                    .frame(height: 8)
                    Text(bridge.previewStatus.isEmpty ? "Preview follows the planned route at 4 mph." : bridge.previewStatus)
                        .font(.caption).foregroundColor(.secondary)
                }
                .padding(.horizontal, 16)

                // Play/Pause + Restart
                HStack(spacing: 10) {
                    Button {
                        if bridge.previewPlaying { bridge.pausePreview() }
                        else { bridge.startPreview() }
                    } label: {
                        Label(bridge.previewPlaying ? "Pause" : "Play",
                              systemImage: bridge.previewPlaying ? "pause.fill" : "play.fill")
                            .font(.system(size: 15, weight: .semibold))
                            .frame(maxWidth: .infinity).frame(height: 46)
                            .background(accent).foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    Button { bridge.restartPreview() } label: {
                        Image(systemName: "arrow.counterclockwise")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(accent)
                            .frame(width: 46, height: 46)
                            .background(Color(.systemGray6))
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                }
                .padding(.horizontal, 16)

                // Follow preview toggle
                Toggle(isOn: Binding(
                    get: { followPreview },
                    set: { v in followPreview = v; bridge.setFollowPreview(v) }
                )) {
                    Label("Follow preview car", systemImage: "car.fill")
                        .font(.subheadline)
                }
                .padding(.horizontal, 16)

                // Speed picker
                HStack {
                    Text("Speed").font(.subheadline).foregroundColor(.secondary)
                    Spacer()
                    Picker("Speed", selection: $previewSpeed) {
                        Text("8×").tag(8)
                        Text("16×").tag(16)
                        Text("32×").tag(32)
                        Text("64×").tag(64)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 200)
                    .onChange(of: previewSpeed) { _, new in bridge.setPreviewSpeed(new) }
                }
                .padding(.horizontal, 16)
            }
        }
    }

    // MARK: - Loading

    private var loadingRow: some View {
        HStack(spacing: 10) {
            ProgressView().scaleEffect(0.85)
            Text("Loading graph…").font(.subheadline).foregroundColor(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
    }

    // MARK: - Drag gesture

    private var dragGesture: some Gesture {
        DragGesture()
            .onEnded { v in
                let vel = -v.predictedEndTranslation.height
                withAnimation(.spring(response: 0.32, dampingFraction: 0.78)) {
                    if vel > 300 {
                        sheetHeight = sheetHeight < halfH ? halfH : fullH
                    } else if vel < -300 {
                        sheetHeight = sheetHeight > halfH ? halfH : peekH
                    } else {
                        let target = sheetHeight - v.translation.height
                        let snaps = [peekH, halfH, fullH]
                        sheetHeight = snaps.min(by: { abs($0 - target) < abs($1 - target) })!
                    }
                }
            }
    }

    // MARK: - Helpers

    private func planRoute() {
        dismissKeyboard()
        activeField = nil
        bridge.suggestions = []
        bridge.planRoute(start: startText, goal: goalText)
        withAnimation { activeTab = .route; sheetHeight = halfH }
    }

    private func switchMap(_ map: NavMap) {
        dismissKeyboard()
        activeField = nil
        bridge.suggestions = []
        bridge.routeInfo = nil
        bridge.setMap(map.rawValue)
        startText = map.defaultStart
        goalText = ""
        withAnimation {
            activeTab = .route
            sheetHeight = halfH
        }
    }

    private func dismissKeyboard() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    private func handleGPXImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            guard let url = urls.first else { return }
            gpxNav.loadAndStart(url: url, name: url.deletingPathExtension().lastPathComponent)
        case .failure(let error):
            gpxNav.lastError = error.localizedDescription
        }
    }

    @ViewBuilder
    private func gpxNavOverlay(safeTop: CGFloat) -> some View {
        VStack {
            if gpxNav.isNavigating {
                HStack(spacing: 10) {
                    Image(systemName: "location.north.line.fill").foregroundColor(accent)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(gpxNav.currentInstruction.isEmpty ? "Navigating GPX" : gpxNav.currentInstruction)
                            .font(.headline).lineLimit(2)
                        if gpxNav.distanceToNext > 0 {
                            Text("in \(Int(gpxNav.distanceToNext.rounded())) m · \(Int(gpxNav.remainingDistance.rounded())) m left")
                                .font(.caption).foregroundColor(.secondary)
                        }
                    }
                    Spacer()
                    Button { gpxNav.repeatInstruction() } label: {
                        Image(systemName: "speaker.wave.2.fill").font(.title3)
                    }
                    Button { gpxNav.stop() } label: {
                        Image(systemName: "xmark.circle.fill").font(.title3).foregroundColor(.secondary)
                    }
                }
                .padding(12)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal, 12)
                .padding(.top, safeTop + 8)
            } else {
                HStack(spacing: 8) {
                    Button { showGPXImporter = true } label: {
                        Label("Start Navigation", systemImage: "location.north.line.fill")
                            .font(.system(size: 15, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 18).padding(.vertical, 12)
                            .background(accent, in: Capsule())
                            .overlay(Capsule().stroke(.white.opacity(0.35), lineWidth: 1))
                            .shadow(color: .black.opacity(0.22), radius: 10, x: 0, y: 4)
                    }
                    if let err = gpxNav.lastError {
                        Text(err).font(.caption2).foregroundColor(.red).lineLimit(2)
                            .padding(.horizontal, 8).padding(.vertical, 6)
                            .background(.ultraThinMaterial, in: Capsule())
                    }
                    Spacer()
                }
                .padding(.leading, 12)
                .padding(.top, safeTop + 58)
            }
            Spacer()
        }
    }

    private func zoomButton(icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .medium))
                .frame(width: 44, height: 44)
        }
        .foregroundColor(accent)
    }
}
