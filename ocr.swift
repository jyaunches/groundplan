// Usage: swift ocr.swift <image_path>
// Prints recognized text from the image using macOS Vision framework.
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count >= 2 else {
    FileHandle.standardError.write("usage: swift ocr.swift <image>\n".data(using: .utf8)!)
    exit(2)
}

let path = CommandLine.arguments[1]
let url = URL(fileURLWithPath: path)

guard let nsImage = NSImage(contentsOf: url),
      let tiff = nsImage.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let cgImage = bitmap.cgImage else {
    FileHandle.standardError.write("failed to load image: \(path)\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest { req, err in
    if let err = err {
        FileHandle.standardError.write("vision error: \(err)\n".data(using: .utf8)!)
        exit(1)
    }
    guard let results = req.results as? [VNRecognizedTextObservation] else { return }
    // Sort top-to-bottom, left-to-right for readability.
    let sorted = results.sorted { (a, b) -> Bool in
        let ay = a.boundingBox.origin.y
        let by = b.boundingBox.origin.y
        if abs(ay - by) > 0.01 { return ay > by }
        return a.boundingBox.origin.x < b.boundingBox.origin.x
    }
    for obs in sorted {
        guard let top = obs.topCandidates(1).first else { continue }
        let bb = obs.boundingBox
        // Print: y x text   (y/x normalized 0..1; y measured from bottom)
        print(String(format: "%.4f\t%.4f\t%.4f\t%.4f\t%@",
                     bb.origin.y, bb.origin.x, bb.size.height, bb.size.width, top.string))
    }
}
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("perform failed: \(error)\n".data(using: .utf8)!)
    exit(1)
}
