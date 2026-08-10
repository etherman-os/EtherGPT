import Cocoa

struct CommandResult {
    let status: Int32
    let output: String
}

func run(_ executable: String, _ arguments: [String]) -> CommandResult {
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
        return CommandResult(
            status: process.terminationStatus,
            output: String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        )
    } catch {
        return CommandResult(status: 1, output: error.localizedDescription)
    }
}

func fail(_ title: String, _ result: CommandResult) -> Never {
    NSApp.setActivationPolicy(.regular)
    NSApp.activate(ignoringOtherApps: true)
    let alert = NSAlert()
    alert.alertStyle = .critical
    alert.messageText = title
    alert.informativeText = result.output.isEmpty ? "Exit code \(result.status)" : result.output
    alert.runModal()
    exit(result.status == 0 ? 1 : result.status)
}

let home = FileManager.default.homeDirectoryForCurrentUser.path
let cli = "\(home)/.local/bin/ethergpt"
let gatewayPlist = "\(home)/Library/LaunchAgents/org.ethergpt.gateway.plist"
let menuPlist = "\(home)/Library/LaunchAgents/org.ethergpt.menu.plist"
let domain = "gui/\(getuid())"
let menuService = "\(domain)/org.ethergpt.menu"

guard FileManager.default.isExecutableFile(atPath: cli) else {
    fail("EtherGPT command not found", CommandResult(status: 1, output: cli))
}
guard FileManager.default.fileExists(atPath: menuPlist) else {
    fail("EtherGPT menu is not installed", CommandResult(status: 1, output: menuPlist))
}

let gateway: CommandResult
if FileManager.default.fileExists(atPath: gatewayPlist) {
    gateway = run(cli, ["service", "enable"])
} else {
    gateway = run(cli, ["service", "install", "--scope", "user"])
}
if gateway.status != 0 { fail("Could not start EtherGPT gateway", gateway) }

let enabled = run("/bin/launchctl", ["enable", menuService])
if enabled.status != 0 { fail("Could not enable EtherGPT menu", enabled) }

let loaded = run("/bin/launchctl", ["print", menuService]).status == 0
if !loaded {
    let bootstrapped = run("/bin/launchctl", ["bootstrap", domain, menuPlist])
    if bootstrapped.status != 0 { fail("Could not load EtherGPT menu", bootstrapped) }
}

func setupRequired() -> Bool? {
    guard let url = URL(string: "http://127.0.0.1:8766/api/status"),
          let data = try? Data(contentsOf: url),
          let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let complete = payload["setup_complete"] as? Bool else { return nil }
    return !complete
}

for _ in 0..<40 {
    if let required = setupRequired() {
        if required {
            NSWorkspace.shared.open(URL(string: "http://127.0.0.1:8766/ui")!)
        }
        break
    }
    Thread.sleep(forTimeInterval: 0.25)
}

exit(0)
