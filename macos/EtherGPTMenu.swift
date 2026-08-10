import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var timer: Timer?
    private let cli = NSString(string: "~/.local/bin/ethergpt").expandingTildeInPath
    private let dashboard = URL(string: "http://127.0.0.1:8766/ui")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "EtherGPT …"
        buildMenu()
        refreshStatus()
        timer = Timer.scheduledTimer(withTimeInterval: 4.0, repeats: true) { [weak self] _ in
            self?.refreshStatus()
        }
    }

    private func item(_ title: String, _ action: Selector) -> NSMenuItem {
        let result = NSMenuItem(title: title, action: action, keyEquivalent: "")
        result.target = self
        return result
    }

    private func buildMenu() {
        let menu = NSMenu()
        let status = NSMenuItem(title: "Checking gateway and tunnel…", action: nil, keyEquivalent: "")
        status.isEnabled = false
        status.tag = 100
        menu.addItem(status)
        menu.addItem(.separator())
        menu.addItem(item("Open Dashboard", #selector(openDashboard)))
        menu.addItem(item("Start", #selector(startService)))
        menu.addItem(item("Restart", #selector(restartService)))
        menu.addItem(item("Stop", #selector(stopService)))
        menu.addItem(.separator())
        menu.addItem(item("Run Doctor in Terminal", #selector(runDoctor)))
        menu.addItem(item("Open Logs", #selector(openLogs)))
        menu.addItem(.separator())
        menu.addItem(item("Quit Menu (service keeps running)", #selector(quit)))
        statusItem.menu = menu
    }

    private func fetch(_ url: URL) -> Bool {
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5
        let semaphore = DispatchSemaphore(value: 0)
        var ok = false
        URLSession.shared.dataTask(with: request) { _, response, _ in
            if let http = response as? HTTPURLResponse { ok = (200..<300).contains(http.statusCode) }
            semaphore.signal()
        }.resume()
        _ = semaphore.wait(timeout: .now() + 2)
        return ok
    }

    private func refreshStatus() {
        DispatchQueue.global(qos: .utility).async { [weak self] in
            guard let self = self else { return }
            let gateway = self.fetch(URL(string: "http://127.0.0.1:8766/readyz")!)
            let tunnel = self.fetch(URL(string: "http://127.0.0.1:8088/readyz")!)
            DispatchQueue.main.async {
                if gateway && tunnel {
                    self.statusItem.button?.title = "EtherGPT ✓"
                    self.statusItem.menu?.item(withTag: 100)?.title = "Gateway ✓   Tunnel ✓"
                } else if gateway {
                    self.statusItem.button?.title = "EtherGPT !"
                    self.statusItem.menu?.item(withTag: 100)?.title = "Gateway ✓   Tunnel offline"
                } else {
                    self.statusItem.button?.title = "EtherGPT OFF"
                    self.statusItem.menu?.item(withTag: 100)?.title = "Gateway offline"
                }
            }
        }
    }

    private func run(_ arguments: [String]) {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self, FileManager.default.isExecutableFile(atPath: self.cli) else { return }
            let process = Process()
            process.executableURL = URL(fileURLWithPath: self.cli)
            process.arguments = arguments
            try? process.run()
            process.waitUntilExit()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.refreshStatus() }
        }
    }

    private func terminal(_ command: String) {
        let escaped = command.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        let script = "tell application \"Terminal\"\nactivate\ndo script \"\(escaped)\"\nend tell"
        NSAppleScript(source: script)?.executeAndReturnError(nil)
    }

    @objc private func openDashboard() { NSWorkspace.shared.open(dashboard) }
    @objc private func startService() { run(["service", "start"]) }
    @objc private func restartService() { run(["service", "restart"]) }
    @objc private func stopService() { run(["service", "stop"]) }
    @objc private func runDoctor() { terminal("\"\(cli)\" doctor; read -n 1") }
    @objc private func openLogs() {
        NSWorkspace.shared.open(URL(fileURLWithPath: NSString(string: "~/Library/Logs/EtherGPT").expandingTildeInPath))
    }
    @objc private func quit() { NSApp.terminate(nil) }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.run()
