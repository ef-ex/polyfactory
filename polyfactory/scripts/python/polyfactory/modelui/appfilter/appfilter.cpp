// modelUI input layer: a tiny C++ application event filter (Windows build of the Maya surface project's appfilter).
//
// Why C++: a Python filter on the QApplication makes PySide wrap EVERY QObject that receives ANY event before the Python
// code runs (getWrapperForQObject sets a dynamic property on it, which sends one more event through the filter); for
// objects Houdini is building or tearing down that crashed Houdini (Maya surface project, T10). This filter looks at the
// event type in C++ and calls Python only for the input types the layer asked for, passing raw pointers: Python never
// converts the receiving QObject.
//
// It is installed at run time, after Houdini's own application filter (Qt runs the newest one first), so it sees input
// before Houdini does. Build: build.bat (MSVC + Houdini's Qt headers). Load: ctypes (input_layer.py).
#include <QtCore/QCoreApplication>
#include <QtCore/QEvent>
#include <QtCore/QObject>

#include <set>

#define PF_EXPORT extern "C" __declspec(dllexport)

typedef int (*pf_callback)(void *receiver, void *event, int type);  // non-zero swallows the event

namespace {

class Filter : public QObject {
public:
    Filter(pf_callback cb, const int *types, int ntypes) : cb_(cb), types_(types, types + ntypes) {}

    bool eventFilter(QObject *receiver, QEvent *event) override
    {
        if (!enabled_ || types_.count(int(event->type())) == 0)
            return false;
        return cb_(receiver, event, int(event->type())) != 0;
    }

    bool enabled_ = true;

private:
    pf_callback cb_;
    std::set<int> types_;
};

}  // namespace

// Install a filter on the running QApplication; returns a handle for pf_uninstall (null without an application).
PF_EXPORT void *pf_install(pf_callback cb, const int *types, int ntypes)
{
    QCoreApplication *app = QCoreApplication::instance();
    if (app == nullptr || cb == nullptr)
        return nullptr;
    auto *f = new Filter(cb, types, ntypes);
    app->installEventFilter(f);
    return f;
}

// Stop calling back at once and remove the filter. The callback is never called after this returns.
PF_EXPORT void pf_uninstall(void *handle)
{
    auto *f = static_cast<Filter *>(handle);
    if (f == nullptr)
        return;
    f->enabled_ = false;
    if (QCoreApplication *app = QCoreApplication::instance())
        app->removeEventFilter(f);
    delete f;
}
