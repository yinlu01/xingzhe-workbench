import Cocoa
import WebKit
import UserNotifications

// ============================================================
// 行者工作台 · macOS 桌面应用（Mac 横屏版 v4）
// Swift + WKWebView：原生通知桥接 + JS 错误拦截 + 攀岩图标
// ============================================================

// MARK: - 日志
func log(_ msg: String) {
    let line = "[\(Date())] \(msg)\n"
    guard let data = line.data(using: .utf8) else { return }
    if let fh = FileHandle(forWritingAtPath: "/tmp/xz_app.log") {
        fh.seekToEndOfFile()
        fh.write(data)
        try? fh.close()
    } else {
        FileManager.default.createFile(atPath: "/tmp/xz_app.log", contents: data)
    }
}

// MARK: - 服务器管理器
class ServerManager {
    static let shared = ServerManager()

    let checkURL = URL(string: "http://127.0.0.1:8765/mac-dashboard.html")!
    let serverScript = "/Users/yinlu01/WorkBuddy/2026-08-06-13-47-58/server.py"
    let pythonPath = "/Users/yinlu01/.workbuddy/binaries/python/envs/default/bin/python"

    private var serverProcess: Process?
    private var didStartServer = false

    func isServerRunning() -> Bool {
        let semaphore = DispatchSemaphore(value: 0)
        var running = false
        let config = URLSessionConfiguration.ephemeral
        config.connectionProxyDictionary = [:]
        let session = URLSession(configuration: config)
        var request = URLRequest(url: checkURL)
        request.timeoutInterval = 2
        let task = session.dataTask(with: request) { _, resp, _ in
            if let http = resp as? HTTPURLResponse, http.statusCode == 200 {
                running = true
            }
            semaphore.signal()
        }
        task.resume()
        _ = semaphore.wait(timeout: .now() + 3)
        return running
    }

    func ensureServer() {
        if isServerRunning() {
            log("[Server] 服务器已在运行")
            return
        }
        log("[Server] 服务器未运行，正在启动...")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = [serverScript]
        do {
            try process.run()
            serverProcess = process
            didStartServer = true
            log("[Server] 服务器已启动 (PID \(process.processIdentifier))")
        } catch {
            log("[Server] 启动失败: \(error.localizedDescription)")
        }
    }

    func stopServerIfOwned() {
        if didStartServer, let p = serverProcess {
            p.terminate()
            log("[Server] 已停止自启动的服务器")
        }
    }
}

// MARK: - 导航代理
final class NavDelegate: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        log("[WebView] 加载失败: \(error.localizedDescription)，2 秒后重试")
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            let url = URL(string: "http://127.0.0.1:8765/mac-dashboard.html")!
            webView.load(URLRequest(url: url))
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        log("[WebView] 页面加载完成")
        // 页面加载完成后，首次触发通知检查
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            webView.evaluateJavaScript("window.nativeCheckReminders && window.nativeCheckReminders();") { _, _ in }
        }
    }
}

// MARK: - 窗口代理
final class WinDelegate: NSObject, NSWindowDelegate {
    func windowWillClose(_ notification: Notification) {
        ServerManager.shared.stopServerIfOwned()
        NSApp.terminate(nil)
    }
}

// MARK: - 通知管理器（原生 macOS 通知桥接）
final class NotificationManager: NSObject, UNUserNotificationCenterDelegate, WKScriptMessageHandler {
    static let shared = NotificationManager()
    private var lastNotifiedBody: String = ""
    private var notificationBridgeRegistered = false

    func setup() {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if let error = error {
                log("[Notify] 通知授权失败: \(error.localizedDescription)")
            } else {
                log("[Notify] 通知授权: \(granted ? "已授权" : "被拒绝")")
            }
        }
    }

    // WKScriptMessageHandler：接收 JS 发送的待办/逾期数据
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let dict = message.body as? [String: Any] else { return }
        let overdueTasks = dict["overdueTasks"] as? Int ?? 0
        let todayTasks = dict["todayTasks"] as? Int ?? 0
        let overdueContacts = dict["overdueContacts"] as? Int ?? 0
        let exerciseMsg = dict["exerciseMsg"] as? String ?? ""
        let studyMsg = dict["studyMsg"] as? String ?? ""
        let reviewMsg = dict["reviewMsg"] as? String ?? ""

        var parts: [String] = []
        if overdueTasks > 0 { parts.append("\(overdueTasks) 个任务已逾期") }
        if todayTasks > 0 { parts.append("\(todayTasks) 个任务今天截止") }
        if overdueContacts > 0 { parts.append("\(overdueContacts) 位联系人该联系了") }
        if !exerciseMsg.isEmpty { parts.append(exerciseMsg) }
        if !studyMsg.isEmpty { parts.append(studyMsg) }
        if !reviewMsg.isEmpty { parts.append(reviewMsg) }

        guard !parts.isEmpty else { return }
        let body = parts.joined(separator: "，")
        if body == lastNotifiedBody { return }
        lastNotifiedBody = body

        let center = UNUserNotificationCenter.current()
        let content = UNMutableNotificationContent()
        content.title = "行者工作台提醒"
        content.body = body
        content.sound = .default
        content.badge = 1
        let request = UNNotificationRequest(identifier: "xingzhe-todo-\(Date().timeIntervalSince1970)", content: content, trigger: nil)
        center.add(request) { error in
            if let error = error {
                log("[Notify] 发送通知失败: \(error.localizedDescription)")
            } else {
                log("[Notify] 已发送: \(body)")
            }
        }
    }

    // 前台时也显示通知横幅
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .badge])
    }

    // 通知桥接脚本：注入到页面，让 JS 可以调用 native 通知
    var bridgeScript: WKUserScript {
        let js = """
        (function(){
            window.nativeCheckReminders = function(){
                try{
                    var t = new Date().toISOString().slice(0,10);
                    var tasks = JSON.parse(localStorage.getItem('wb_life_tasks') || '[]');
                    var undone = tasks.filter(function(x){ return !x.dn; });
                    var overdueTasks = undone.filter(function(x){ return x.d < t; }).length;
                    var todayTasks = undone.filter(function(x){ return x.d === t; }).length;
                    var contacts = JSON.parse(localStorage.getItem('wb_life_contacts') || '[]');
                    var nowDays = function(d){ return Math.floor((new Date()-new Date(d))/86400000); };
                    var overdueContacts = contacts.filter(function(c){ return nowDays(c.lc) > c.iv; }).length;
                    var ch = JSON.parse(localStorage.getItem('wb_life_study_checkin') || '{}');
                    var books = JSON.parse(localStorage.getItem('wb_life_books') || '[]');
                    var exs = JSON.parse(localStorage.getItem('wb_life_exercises') || '[]');
                    // 今日运动：具体训练内容
                    var exerciseMsg = '';
                    var todayEx = exs.filter(function(e){ return e.d === t; });
                    if(!todayEx.length){
                        var EX_WEEK_PLAN = {1:'推日·胸肩三头',2:'搏击操',3:'拉日·背二头',4:'核心训练',5:'腿日·腿臀',6:'有氧+吊杠测试',0:''};
                        var title = EX_WEEK_PLAN[new Date().getDay()] || '';
                        if(title) exerciseMsg = '今日运动：' + title;
                        else exerciseMsg = '今日休息：主动恢复';
                    }
                    // 学习打卡：优先微信读书在读，其次书架
                    var studyMsg = '';
                    if(books.length && !ch[t]){
                        var wr = null;
                        try{ wr = JSON.parse(localStorage.getItem('wb_life_weread') || 'null'); }catch(e){}
                        var wrBook = wr && wr.inProgressBooks && wr.inProgressBooks[0];
                        if(wrBook) studyMsg = '读书打卡：《' + wrBook.title + '》已读' + wrBook.readingProgress + '%';
                        else{
                            var reading = null;
                            for(var i=0;i<books.length;i++){ if(books[i].c < books[i].tl){ reading = books[i]; break; } }
                            if(reading) studyMsg = '读书打卡：《' + reading.ti + '》' + reading.c + '/' + reading.tl + '页';
                            else studyMsg = '今天还没学习打卡';
                        }
                    }
                    // 复盘提醒：21:30 后还没写今日复盘（状态由页面镜像到 localStorage）
                    var reviewDone = false;
                    try{ reviewDone = localStorage.getItem('wb_life_review_today') === '1'; }catch(e){}
                    var reviewMsg = '';
                    if(!reviewDone){
                        var nowH = new Date().getHours(), nowM = new Date().getMinutes();
                        if(nowH === 21 && nowM >= 30) reviewMsg = '该写今日复盘了';
                    }
                    var data = {
                        overdueTasks: overdueTasks,
                        todayTasks: todayTasks,
                        overdueContacts: overdueContacts,
                        exerciseMsg: exerciseMsg,
                        studyMsg: studyMsg,
                        reviewMsg: reviewMsg
                    };
                    if(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.xingzheNotify){
                        window.webkit.messageHandlers.xingzheNotify.postMessage(data);
                    }
                }catch(e){ console.log('nativeCheckReminders error:', e); }
            };
        })();
        """
        return WKUserScript(source: js, injectionTime: .atDocumentEnd, forMainFrameOnly: true)
    }

    // 周期性触发 JS 检查（每 10 分钟）
    func startPeriodicCheck(webView: WKWebView) {
        Timer.scheduledTimer(withTimeInterval: 600, repeats: true) { _ in
            webView.evaluateJavaScript("window.nativeCheckReminders && window.nativeCheckReminders();") { _, _ in }
        }
    }
}

// ============================================================
// MARK: - 入口
// ============================================================
let app = NSApplication.shared
app.setActivationPolicy(.regular)

// 1. 创建窗口（横屏 1280x840）
let mainWindow = NSWindow(
    contentRect: NSRect(x: 0, y: 0, width: 1280, height: 840),
    styleMask: [.titled, .closable, .miniaturizable, .resizable],
    backing: .buffered,
    defer: false
)
mainWindow.title = "行者工作台 · Mac"
mainWindow.minSize = NSSize(width: 960, height: 640)
mainWindow.center()
mainWindow.backgroundColor = NSColor.windowBackgroundColor

// 2. 创建 WebView 配置（注入 JS 错误拦截 + 通知桥接）
let webViewConfig = WKWebViewConfiguration()

// 2a. JS 错误拦截脚本
let errorScript = """
window.onerror = function(msg, url, line, col, error) {
    console.log('XZ_JS_ERROR: ' + msg + ' at line ' + line);
    return true;
};
window.addEventListener('unhandledrejection', function(e) {
    console.log('XZ_JS_REJECTION: ' + e.reason);
});
"""
let errorUserScript = WKUserScript(source: errorScript, injectionTime: .atDocumentStart, forMainFrameOnly: true)
webViewConfig.userContentController.addUserScript(errorUserScript)

// 2b. 通知桥接脚本
webViewConfig.userContentController.addUserScript(NotificationManager.shared.bridgeScript)

// 2c. 注册消息处理器
webViewConfig.userContentController.add(NotificationManager.shared, name: "xingzheNotify")

let webView = WKWebView(frame: mainWindow.contentView!.bounds, configuration: webViewConfig)
webView.autoresizingMask = [.width, .height]
let navDelegate = NavDelegate()
webView.navigationDelegate = navDelegate
webView.allowsBackForwardNavigationGestures = true
webView.customUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

// 3. 设置窗口内容并显示
mainWindow.contentView?.addSubview(webView)
mainWindow.makeKeyAndOrderFront(nil)
let winDelegate = WinDelegate()
mainWindow.delegate = winDelegate
NSApp.activate(ignoringOtherApps: true)

log("[App] 窗口已创建 frame=\(mainWindow.frame) visible=\(mainWindow.isVisible)")

// 4. 初始化通知中心
NotificationManager.shared.setup()

// 5. 启动周期性检查（页面加载后触发）
NotificationManager.shared.startPeriodicCheck(webView: webView)

// 6. 确保服务器运行
ServerManager.shared.ensureServer()

// 7. 后台等待服务器就绪后加载页面
DispatchQueue.global().async {
    for _ in 0..<20 {
        if ServerManager.shared.isServerRunning() { break }
        usleep(1_000_000)
    }
    DispatchQueue.main.async {
        let url = URL(string: "http://127.0.0.1:8765/mac-dashboard.html")!
        webView.load(URLRequest(url: url))
    }
}

// 8. 运行主循环
app.run()
