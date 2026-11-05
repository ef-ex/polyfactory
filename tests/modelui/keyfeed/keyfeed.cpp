// Test-only: feed a key to a QWindow through Qt's platform entry points (as the Windows platform plugin does), so the
// real shortcut-override path runs: QWindowSystemInterface::handleShortcutEvent first (QEvent::ShortcutOverride, type
// 51, and QShortcut matching), then the key event itself if no shortcut took it. Used by shortcut_probe.py to see
// whether a key the modelUI input layer swallows can still fire a Houdini hotkey. Build: build_keyfeed.bat.
#include <QtGui/QWindow>
#include <QtGui/qpa/qwindowsysteminterface.h>

// press: 1 = press (shortcut path first), 0 = release. Returns 1 when the shortcut path consumed the press.
extern "C" __declspec(dllexport) int pf_feed_key(void *window, int press, int key, int mods)
{
    QWindow *w = static_cast<QWindow *>(window);
    const Qt::KeyboardModifiers m = Qt::KeyboardModifiers::fromInt(mods);
    int consumed = 0;
    if (press && QWindowSystemInterface::handleShortcutEvent(w, 0, key, m, 0, 0, 0))
        consumed = 1;
    else
        QWindowSystemInterface::handleExtendedKeyEvent(
            w, press ? QEvent::KeyPress : QEvent::KeyRelease, key, m, 0, 0, 0);
    QWindowSystemInterface::flushWindowSystemEvents();
    return consumed;
}
