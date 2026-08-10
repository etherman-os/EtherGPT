import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var timer: Timer?
    private let cli = NSString(string: "~/.local/bin/ethergpt").expandingTildeInPath
    private let servicePlist = NSString(string: "~/Library/LaunchAgents/org.ethergpt.gateway.plist").expandingTildeInPath
    private let menuService = "gui/\(getuid())/org.ethergpt.menu"
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
        menu.addItem(item("Enable & Start (Auto-start ON)", #selector(enableService)))
        menu.addItem(item("Restart", #selector(restartService)))
        menu.addItem(item("Disable & Stop (Auto-start OFF)", #selector(disableService)))
        menu.addItem(.separator())
        menu.addItem(item("Run Doctor in Terminal", #selector(runDoctor)))
        menu.addItem(item("Open Logs", #selector(openLogs)))
        menu.addItem(.separator())
        menu.addItem(item("Quit EtherGPT (Stop & Stay Off)", #selector(quitEtherGPT)))
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

    private func showError(_ title: String, _ message: String) {
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    private func run(_ arguments: [String], label: String) {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            guard FileManager.default.isExecutableFile(atPath: self.cli) else {
                DispatchQueue.main.async {
                    self.showError("EtherGPT command not found", self.cli)
                }
                return
            }
            let process = Process()
            let output = Pipe()
            process.executableURL = URL(fileURLWithPath: self.cli)
            process.arguments = arguments
            process.standardOutput = output
            process.standardError = output
            do {
                try process.run()
                process.waitUntilExit()
                let data = output.fileHandleForReading.readDataToEndOfFile()
                let message = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    if process.terminationStatus != 0 {
                        self.showError("\(label) failed", message.isEmpty ? "Exit code \(process.terminationStatus)" : message)
                    }
                    self.refreshStatus()
                }
            } catch {
                DispatchQueue.main.async {
                    self.showError("\(label) failed", error.localizedDescription)
                }
            }
        }
    }

    private func runSync(_ executable: String, _ arguments: [String]) -> (Int32, String) {
        let process = Process()
        let output = Pipe()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.standardOutput = output
        process.standardError = output
        do {
            try process.run()
            process.waitUntilExit()
            let data = output.fileHandleForReading.readDataToEndOfFile()
            return (
                process.terminationStatus,
                String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            )
        } catch {
            return (1, error.localizedDescription)
        }
    }

    private func terminal(_ command: String) {
        let escaped = command.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        let script = "tell application \"Terminal\"\nactivate\ndo script \"\(escaped)\"\nend tell"
        NSAppleScript(source: script)?.executeAndReturnError(nil)
    }

    @objc private func openDashboard() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let online = self.fetch(URL(string: "http://127.0.0.1:8766/readyz")!)
            DispatchQueue.main.async {
                if online {
                    if !NSWorkspace.shared.open(self.dashboard) {
                        self.showError("Could not open dashboard", self.dashboard.absoluteString)
                    }
                } else {
                    self.showError(
                        "EtherGPT is off",
                        "Choose “Enable & Start (Auto-start ON)” first, then open the dashboard."
                    )
                }
            }
        }
    }
    @objc private func enableService() {
        if FileManager.default.fileExists(atPath: servicePlist) {
            run(["service", "enable"], label: "Enable & Start")
        } else {
            run(["service", "install", "--scope", "user"], label: "Install & Start")
        }
    }
    @objc private func restartService() { run(["service", "restart"], label: "Restart") }
    @objc private func disableService() { run(["service", "disable"], label: "Disable & Stop") }
    @objc private func runDoctor() { terminal("\"\(cli)\" doctor; read -n 1") }
    @objc private func openLogs() {
        NSWorkspace.shared.open(URL(fileURLWithPath: NSString(string: "~/Library/Logs/EtherGPT").expandingTildeInPath))
    }
    @objc private func quitEtherGPT() {
        timer?.invalidate()
        statusItem.button?.title = "EtherGPT stopping…"
        statusItem.menu?.items.forEach { $0.isEnabled = false }

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let stopped = self.runSync(self.cli, ["service", "disable"])
            if stopped.0 != 0 {
                DispatchQueue.main.async {
                    self.showError(
                        "Could not stop EtherGPT",
                        stopped.1.isEmpty ? "Exit code \(stopped.0)" : stopped.1
                    )
                    self.buildMenu()
                    self.refreshStatus()
                }
                return
            }

            let disabled = self.runSync("/bin/launchctl", ["disable", self.menuService])
            if disabled.0 != 0 {
                DispatchQueue.main.async {
                    self.showError(
                        "Could not disable menu auto-start",
                        disabled.1.isEmpty ? "Exit code \(disabled.0)" : disabled.1
                    )
                    self.buildMenu()
                }
                return
            }

            DispatchQueue.main.async { NSApp.terminate(nil) }
        }
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.run()
