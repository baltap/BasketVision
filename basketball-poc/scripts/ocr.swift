// Run Apple Vision text recognition over a list of image paths (one per line).
// Output (TSV): path, recognized text, confidence. One line per recognized text block,
// or an empty text with confidence 0 when nothing was found.
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2 else {
    FileHandle.standardError.write("usage: ocr LIST_FILE\n".data(using: .utf8)!)
    exit(1)
}
let listText = try String(contentsOfFile: args[1], encoding: .utf8)
let paths = listText.split(separator: "\n").map(String.init)

for p in paths {
    autoreleasepool {
        guard let img = NSImage(contentsOfFile: p),
              let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            print("\(p)\t\t0")
            return
        }
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = false
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        try? handler.perform([req])
        let obs = req.results ?? []
        var any = false
        for o in obs {
            if let c = o.topCandidates(1).first {
                let t = c.string.replacingOccurrences(of: "\t", with: " ")
                print("\(p)\t\(t)\t\(c.confidence)")
                any = true
            }
        }
        if !any { print("\(p)\t\t0") }
    }
}
