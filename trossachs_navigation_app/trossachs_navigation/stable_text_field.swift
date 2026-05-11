import SwiftUI
import UIKit

/// A UITextField wrapped in UIViewRepresentable so SwiftUI re-renders
/// never dismiss the keyboard or reset cursor position.
struct StableTextField: UIViewRepresentable {
    let placeholder: String
    @Binding var text: String
    var keepFocus: Bool = false
    var onCommit: () -> Void = {}
    var onChange: (String) -> Void = { _ in }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UITextField {
        let tf = UITextField()
        tf.placeholder = placeholder
        tf.font = .systemFont(ofSize: 16)
        tf.autocorrectionType = .no
        tf.autocapitalizationType = .none
        tf.returnKeyType = .search
        tf.clearButtonMode = .whileEditing
        tf.delegate = context.coordinator
        tf.addTarget(context.coordinator, action: #selector(Coordinator.textChanged), for: .editingChanged)
        return tf
    }

    func updateUIView(_ tf: UITextField, context: Context) {
        if tf.text != text { tf.text = text }
        context.coordinator.keepFocus = keepFocus
    }

    class Coordinator: NSObject, UITextFieldDelegate {
        var parent: StableTextField
        var keepFocus = false
        init(_ parent: StableTextField) { self.parent = parent }

        @objc func textChanged(_ tf: UITextField) {
            let t = tf.text ?? ""
            parent.text = t
            parent.onChange(t)
        }

        func textFieldShouldReturn(_ tf: UITextField) -> Bool {
            parent.onCommit()
            tf.resignFirstResponder()
            return true
        }

        func textFieldShouldEndEditing(_ tf: UITextField) -> Bool {
            // Block resign while suggestions are being shown
            return !keepFocus
        }
    }
}
