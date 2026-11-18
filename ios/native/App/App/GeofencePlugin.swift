import Foundation
import Capacitor
import CoreLocation
import UserNotifications

/// Walk NYC geofencing: monitors the active tour's stops so arrivals fire with the phone
/// locked or in a pocket.
///
/// JS API (window.Capacitor.Plugins.Geofence):
///   requestPermission()                                          -> {status, notifications}
///   setStops({stops:[{id:"fidi:3", lat, lng, radius, title?}]})  replaces monitored stops
///   clear()
///   event "enter" {id, timestamp, tapped}
///
/// Uses CLMonitor (iOS 17+). The older CLLocationManager.startMonitoring(for:) fails with
/// kCLErrorRegionMonitoringFailure on iOS 27 (seen in the Simulator), so it isn't used.
///
/// v1 arrival handling: when the app isn't in the foreground, post a local notification
/// ("Arrived: 4. Wall Street", "Tap to play"). The "enter" event always goes to JS too;
/// if the WebView is alive (e.g. audio is playing) it plays or queues the stop itself.
/// Tapping the notification re-sends "enter" with tapped:true.
@objc(GeofencePlugin)
public class GeofencePlugin: CAPPlugin, CAPBridgedPlugin, CLLocationManagerDelegate, UNUserNotificationCenterDelegate {
    public let identifier = "GeofencePlugin"
    public let jsName = "Geofence"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "requestPermission", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setStops", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clear", returnType: CAPPluginReturnPromise),
    ]

    static let minRadius: CLLocationDistance = 100   // geofences are unreliable below ~100 m
    static let maxRegions = 20                       // iOS per-app limit
    static let monitorName = "WalkNYCStops"
    static let titlesKey = "walknyc.geofence.titles"

    private var manager: CLLocationManager!
    private var monitor: CLMonitor?
    private var monitorReady: [(CLMonitor) async -> Void] = []
    private var pendingPermissionCalls: [CAPPluginCall] = []
    private var permissionTimer: Timer?

    override public func load() {
        DispatchQueue.main.async {
            self.manager = CLLocationManager()
            self.manager.delegate = self
            UNUserNotificationCenter.current().delegate = self
        }
        // Open the monitor at launch so events that relaunch the app in the background are delivered.
        Task { await self.startMonitor() }
    }

    private func startMonitor() async {
        let m = await CLMonitor(Self.monitorName)
        await MainActor.run {
            self.monitor = m
            let waiting = self.monitorReady
            self.monitorReady.removeAll()
            for w in waiting { Task { await w(m) } }
        }
        do {
            for try await event in await m.events {
                NSLog("Geofence: \(event.identifier) -> \(Self.describe(event))")
                if event.state == .satisfied {
                    await MainActor.run { self.didArrive(id: event.identifier) }
                }
            }
        } catch {
            NSLog("Geofence: monitor events ended: \(error.localizedDescription)")
        }
    }

    /// Runs `work` once the CLMonitor exists (it's created asynchronously at launch).
    private func withMonitor(_ work: @escaping (CLMonitor) async -> Void) {
        DispatchQueue.main.async {
            if let m = self.monitor { Task { await work(m) } } else { self.monitorReady.append(work) }
        }
    }

    // MARK: - JS methods

    @objc func requestPermission(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
            switch self.manager.authorizationStatus {
            case .notDetermined:
                self.pendingPermissionCalls.append(call)
                self.manager.requestWhenInUseAuthorization()   // then upgraded to Always in the delegate
            case .authorizedWhenInUse:
                // iOS only shows the Always prompt once; if it doesn't, no delegate callback comes.
                self.pendingPermissionCalls.append(call)
                self.askForAlways()
            default:
                self.resolve(call)
            }
        }
    }

    @objc func setStops(_ call: CAPPluginCall) {
        guard let stops = call.getArray("stops") as? [[String: Any]] else {
            call.reject("stops must be an array of {id, lat, lng, radius}")
            return
        }
        var titles: [String: String] = [:]
        var conditions: [(String, CLMonitor.CircularGeographicCondition)] = []
        for s in stops.prefix(Self.maxRegions) {
            guard let id = s["id"] as? String,
                  let lat = (s["lat"] as? NSNumber)?.doubleValue,
                  let lng = (s["lng"] as? NSNumber)?.doubleValue else { continue }
            let r = max(Self.minRadius, (s["radius"] as? NSNumber)?.doubleValue ?? 0)
            conditions.append((id, CLMonitor.CircularGeographicCondition(
                center: CLLocationCoordinate2D(latitude: lat, longitude: lng), radius: r)))
            if let t = s["title"] as? String { titles[id] = t }
        }
        UserDefaults.standard.set(titles, forKey: Self.titlesKey)
        withMonitor { m in
            for id in await m.identifiers { await m.remove(id) }
            // assuming: .unsatisfied, so a stop you're already standing at fires once monitoring starts.
            for (id, c) in conditions { await m.add(c, identifier: id, assuming: .unsatisfied) }
            NSLog("Geofence: monitoring \(conditions.count) stops")
            call.resolve(["registered": conditions.map { $0.0 }, "dropped": max(0, stops.count - Self.maxRegions)])
        }
    }

    @objc func clear(_ call: CAPPluginCall) {
        UserDefaults.standard.removeObject(forKey: Self.titlesKey)
        withMonitor { m in
            for id in await m.identifiers { await m.remove(id) }
            call.resolve()
        }
    }

    /// State plus iOS's reasons when a stop is .unmonitored (shows up in Console.app / Xcode logs).
    static func describe(_ e: CLMonitor.Event) -> String {
        let state: String
        switch e.state {
        case .satisfied: state = "satisfied"
        case .unsatisfied: state = "unsatisfied"
        case .unknown: state = "unknown"
        default: state = "unmonitored"
        }
        var reasons: [String] = []
        guard #available(iOS 18, *) else { return state }
        if e.authorizationDenied { reasons.append("authorizationDenied") }
        if e.authorizationDeniedGlobally { reasons.append("locationServicesOff") }
        if e.authorizationRestricted { reasons.append("restricted") }
        if e.insufficientlyInUse { reasons.append("insufficientlyInUse") }
        if e.accuracyLimited { reasons.append("accuracyLimited (turn on Precise Location)") }
        if e.conditionUnsupported { reasons.append("conditionUnsupported") }
        if e.conditionLimitExceeded { reasons.append("conditionLimitExceeded") }
        if e.persistenceUnavailable { reasons.append("persistenceUnavailable") }
        if e.serviceSessionRequired { reasons.append("serviceSessionRequired") }
        return state + (reasons.isEmpty ? "" : " [" + reasons.joined(separator: ", ") + "]")
    }

    // MARK: - Arrival

    private func didArrive(id: String) {
        NSLog("Geofence: arrived \(id) (app state \(UIApplication.shared.applicationState.rawValue))")
        notifyListeners("enter", data: ["id": id, "timestamp": Date().timeIntervalSince1970 * 1000, "tapped": false])
        if UIApplication.shared.applicationState != .active {
            postArrivalNotification(id: id)
        }
    }

    private func postArrivalNotification(id: String) {
        let titles = UserDefaults.standard.dictionary(forKey: Self.titlesKey) as? [String: String] ?? [:]
        let content = UNMutableNotificationContent()
        content.title = "Arrived: " + (titles[id] ?? "next stop")
        content.body = "Tap to play"
        content.sound = .default
        content.userInfo = ["walknycStop": id]
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "arrive-" + id, content: content, trigger: nil))
    }

    public func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                       withCompletionHandler completionHandler: @escaping () -> Void) {
        if let id = response.notification.request.content.userInfo["walknycStop"] as? String {
            // retainUntilConsumed: on a cold launch the WebView may not have added its listener yet.
            notifyListeners("enter", data: ["id": id, "timestamp": Date().timeIntervalSince1970 * 1000, "tapped": true],
                            retainUntilConsumed: true)
        }
        completionHandler()
    }

    public func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                       withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    // MARK: - Permission

    public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus == .authorizedWhenInUse && !pendingPermissionCalls.isEmpty && permissionTimer == nil {
            askForAlways()   // step two: Always is what lets stops fire with the phone locked
            return
        }
        if manager.authorizationStatus != .notDetermined { resolvePermissionCalls() }
    }

    private func askForAlways() {
        manager.requestAlwaysAuthorization()
        permissionTimer?.invalidate()
        permissionTimer = Timer.scheduledTimer(withTimeInterval: 4, repeats: false) { _ in self.resolvePermissionCalls() }
    }

    private func statusString() -> String {
        switch manager.authorizationStatus {
        case .authorizedAlways: return "always"
        case .authorizedWhenInUse: return "whenInUse"
        case .denied: return "denied"
        case .restricted: return "restricted"
        default: return "notDetermined"
        }
    }

    private func resolve(_ call: CAPPluginCall) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            let ok = settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional
            DispatchQueue.main.async { call.resolve(["status": self.statusString(), "notifications": ok]) }
        }
    }

    private func resolvePermissionCalls() {
        permissionTimer?.invalidate()
        permissionTimer = nil
        let calls = pendingPermissionCalls
        pendingPermissionCalls.removeAll()
        calls.forEach { resolve($0) }
    }
}
