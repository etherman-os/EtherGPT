import AppKit

let fileManager = FileManager.default
guard CommandLine.arguments.count == 2 else {
    fputs("usage: EtherGPTIconGenerator /path/to/EtherGPT.iconset\n", stderr)
    exit(2)
}

let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try fileManager.createDirectory(at: output, withIntermediateDirectories: true)

func writeIcon(pixelSize: Int, name: String) throws {
    let side = CGFloat(pixelSize)
    let image = NSImage(size: NSSize(width: side, height: side))
    image.lockFocus()

    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: side, height: side).fill()

    let inset = side * 0.045
    let tileRect = NSRect(x: inset, y: inset, width: side - inset * 2, height: side - inset * 2)
    let tile = NSBezierPath(roundedRect: tileRect, xRadius: side * 0.22, yRadius: side * 0.22)

    NSGraphicsContext.current?.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.24)
    shadow.shadowBlurRadius = side * 0.045
    shadow.shadowOffset = NSSize(width: 0, height: -side * 0.025)
    shadow.set()
    let gradient = NSGradient(
        starting: NSColor(calibratedRed: 0.47, green: 0.20, blue: 0.96, alpha: 1),
        ending: NSColor(calibratedRed: 0.08, green: 0.62, blue: 0.95, alpha: 1)
    )!
    gradient.draw(in: tile, angle: -45)
    NSGraphicsContext.current?.restoreGraphicsState()

    let highlightRect = tileRect.insetBy(dx: side * 0.025, dy: side * 0.025)
    let highlight = NSBezierPath(
        roundedRect: highlightRect,
        xRadius: side * 0.19,
        yRadius: side * 0.19
    )
    NSColor.white.withAlphaComponent(0.13).setStroke()
    highlight.lineWidth = max(1, side * 0.012)
    highlight.stroke()

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    let attributes: [NSAttributedString.Key: Any] = [
        .font: NSFont.systemFont(ofSize: side * 0.60, weight: .heavy),
        .foregroundColor: NSColor.white,
        .paragraphStyle: paragraph,
        .kern: -side * 0.025,
    ]
    let letter = "E" as NSString
    let textSize = letter.size(withAttributes: attributes)
    let textRect = NSRect(
        x: 0,
        y: (side - textSize.height) / 2 - side * 0.015,
        width: side,
        height: textSize.height
    )
    letter.draw(in: textRect, withAttributes: attributes)

    image.unlockFocus()
    guard let tiff = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "EtherGPTIcon", code: 1)
    }
    try png.write(to: output.appendingPathComponent(name))
}

let icons: [(Int, String)] = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

for (size, name) in icons {
    try writeIcon(pixelSize: size, name: name)
}
