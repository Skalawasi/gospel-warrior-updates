#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <signal.h>

static NSString *Option(NSString *name) {
    NSArray *args = NSProcessInfo.processInfo.arguments;
    NSUInteger index = [args indexOfObject:name];
    return index != NSNotFound && index + 1 < args.count ? args[index + 1] : nil;
}
static BOOL Flag(NSString *name) {
    return [NSProcessInfo.processInfo.arguments containsObject:name];
}
static NSDictionary *ReadJSON(NSString *path) {
    NSData *data = [NSData dataWithContentsOfFile:path];
    id value = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    return [value isKindOfClass:NSDictionary.class] ? value : @{};
}
static void WriteJSON(NSDictionary *value, NSString *path) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:path options:NSDataWritingAtomic error:nil];
}

@interface GospelApp : NSObject <NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler>
@property NSWindow *window;
@property WKWebView *webView;
@property NSView *loadingView;
@property NSTextField *loadingLabel;
@property NSTask *service;
@property NSFileHandle *serviceLog;
@property NSTimer *startupTimer;
@property NSURL *baseURL;
@property NSString *supportPath;
@property NSString *readyPath;
@property NSString *preferencesPath;
@property NSMutableDictionary *preferences;
@property BOOL terminating;
@property BOOL serviceReady;
@property BOOL testRunning;
@property NSInteger startupTicks;
@property NSInteger testTicks;
@property(strong) id synchronizationActivity;
@end

@implementation GospelApp

- (NSMenuItem *)item:(NSString *)title action:(SEL)action key:(NSString *)key menu:(NSMenu *)menu {
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:title action:action keyEquivalent:key];
    if (action && [self respondsToSelector:action]) item.target = self;
    [menu addItem:item];
    return item;
}
- (NSMenu *)submenu:(NSString *)title parent:(NSMenu *)parent {
    NSMenuItem *item = [[NSMenuItem alloc] initWithTitle:title action:nil keyEquivalent:@""];
    NSMenu *menu = [[NSMenu alloc] initWithTitle:title];
    item.submenu = menu;
    [parent addItem:item];
    return menu;
}
- (void)createMenus {
    NSMenu *bar = [[NSMenu alloc] initWithTitle:@"Main"];
    NSMenu *app = [self submenu:@"Gospel Warrior" parent:bar];
    [self item:@"About Gospel Warrior" action:@selector(about:) key:@"" menu:app];
    [app addItem:NSMenuItem.separatorItem];
    [self item:@"Settings…" action:@selector(settings:) key:@"," menu:app];
    [app addItem:NSMenuItem.separatorItem];
    NSMenu *services = [self submenu:@"Services" parent:app];
    NSApp.servicesMenu = services;
    [app addItem:NSMenuItem.separatorItem];
    [self item:@"Hide Gospel Warrior" action:@selector(hide:) key:@"h" menu:app];
    NSMenuItem *hideOthers = [self item:@"Hide Others" action:@selector(hideOtherApplications:) key:@"h" menu:app];
    hideOthers.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagOption;
    [self item:@"Show All" action:@selector(unhideAllApplications:) key:@"" menu:app];
    [app addItem:NSMenuItem.separatorItem];
    [self item:@"Quit Gospel Warrior" action:@selector(terminate:) key:@"q" menu:app];

    NSMenu *file = [self submenu:@"File" parent:bar];
    [self item:@"Study Library" action:@selector(home:) key:@"l" menu:file];
    [self item:@"Search Studies" action:@selector(search:) key:@"k" menu:file];
    NSMenuItem *saved = [self item:@"Saved Studies" action:@selector(saved:) key:@"b" menu:file];
    saved.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagShift;
    [file addItem:NSMenuItem.separatorItem];
    [self item:@"Refresh Archive" action:@selector(refresh:) key:@"r" menu:file];
    NSMenuItem *check = [self item:@"Check for New Studies" action:@selector(checkUpdates:) key:@"r" menu:file];
    check.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagShift;
    [self item:@"Archive Update Status…" action:@selector(updateStatus:) key:@"" menu:file];
    [self item:@"Update Settings…" action:@selector(updateSettings:) key:@"" menu:file];
    [file addItem:NSMenuItem.separatorItem];
    [self item:@"Show App Data in Finder" action:@selector(showData:) key:@"" menu:file];
    [self item:@"Close Window" action:@selector(performClose:) key:@"w" menu:file];

    NSMenu *navigate = [self submenu:@"Navigate" parent:bar];
    [self item:@"Study Desk" action:@selector(desk:) key:@"1" menu:navigate];
    [self item:@"Study Library" action:@selector(home:) key:@"2" menu:navigate];
    [self item:@"Bible Index" action:@selector(bible:) key:@"3" menu:navigate];
    [self item:@"Study Topics" action:@selector(topics:) key:@"4" menu:navigate];
    [self item:@"Library Updates" action:@selector(updateStatus:) key:@"5" menu:navigate];

    NSMenu *edit = [self submenu:@"Edit" parent:bar];
    [self item:@"Undo" action:@selector(undo:) key:@"z" menu:edit];
    NSMenuItem *redo = [self item:@"Redo" action:@selector(redo:) key:@"z" menu:edit];
    redo.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagShift;
    [edit addItem:NSMenuItem.separatorItem];
    [self item:@"Cut" action:@selector(cut:) key:@"x" menu:edit];
    [self item:@"Copy" action:@selector(copy:) key:@"c" menu:edit];
    [self item:@"Paste" action:@selector(paste:) key:@"v" menu:edit];
    [self item:@"Select All" action:@selector(selectAll:) key:@"a" menu:edit];

    NSMenu *view = [self submenu:@"View" parent:bar];
    [self item:@"Toggle Dark Reading Mode" action:@selector(toggleTheme:) key:@"d" menu:view];
    [self item:@"Larger Reading Text" action:@selector(largerText:) key:@"+" menu:view];
    [self item:@"Smaller Reading Text" action:@selector(smallerText:) key:@"-" menu:view];
    [view addItem:NSMenuItem.separatorItem];
    NSMenuItem *fullscreen = [self item:@"Enter Full Screen" action:@selector(toggleFullScreen:) key:@"f" menu:view];
    fullscreen.keyEquivalentModifierMask = NSEventModifierFlagCommand | NSEventModifierFlagControl;

    NSMenu *window = [self submenu:@"Window" parent:bar];
    [self item:@"Minimize" action:@selector(performMiniaturize:) key:@"m" menu:window];
    [self item:@"Zoom" action:@selector(performZoom:) key:@"" menu:window];
    NSApp.windowsMenu = window;
    NSMenu *help = [self submenu:@"Help" parent:bar];
    [self item:@"Gospel Warrior Help" action:@selector(help:) key:@"" menu:help];
    NSApp.helpMenu = help;
    NSApp.mainMenu = bar;
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    // Keep App Nap from indefinitely throttling synchronization when the app
    // is behind another window. Normal Mac sleep remains available; the service
    // catches up with an overdue check when the computer wakes.
    self.synchronizationActivity = [NSProcessInfo.processInfo beginActivityWithOptions:NSActivityUserInitiatedAllowingIdleSystemSleep reason:@"Keep the Bible study library synchronized while the app is open"];
    [self createMenus];
    NSString *override = Option(@"--profile-dir");
    NSString *support = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES).firstObject;
    self.supportPath = override ?: [support stringByAppendingPathComponent:@"Gospel Warrior"];
    NSError *error = nil;
    if (![NSFileManager.defaultManager createDirectoryAtPath:self.supportPath withIntermediateDirectories:YES attributes:nil error:&error]) {
        [self fatal:error.localizedDescription];
        return;
    }
    self.preferencesPath = [self.supportPath stringByAppendingPathComponent:@"preferences.json"];
    self.preferences = [ReadJSON(self.preferencesPath) mutableCopy];
    self.readyPath = [self.supportPath stringByAppendingPathComponent:[NSString stringWithFormat:@"service-%d.json", getpid()]];

    NSRect screen = NSScreen.mainScreen.visibleFrame;
    NSRect frame = NSMakeRect(0, 0, MIN(1180, screen.size.width - 40), MIN(780, screen.size.height - 40));
    self.window = [[NSWindow alloc] initWithContentRect:frame styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"Gospel Warrior — Study Companion";
    self.window.minSize = NSMakeSize(800, 560);
    self.window.releasedWhenClosed = NO;
    self.window.backgroundColor = [NSColor colorWithCalibratedRed:0.957 green:0.941 blue:0.906 alpha:1];
    [self.window center];
    if (!override) [self.window setFrameAutosaveName:@"GospelWarriorMainWindow"];

    WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
    configuration.websiteDataStore = WKWebsiteDataStore.defaultDataStore;
    [configuration.userContentController addScriptMessageHandler:self name:@"gospelPreferences"];
    [configuration.userContentController addScriptMessageHandler:self name:@"gospelAppearance"];
    self.webView = [[WKWebView alloc] initWithFrame:self.window.contentView.bounds configuration:configuration];
    self.webView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    self.webView.navigationDelegate = self;
    self.webView.UIDelegate = self;
    self.webView.allowsBackForwardNavigationGestures = YES;
    self.webView.hidden = YES;
    [self installPreferenceScript];
    [self.window.contentView addSubview:self.webView];

    self.loadingView = [[NSView alloc] initWithFrame:self.window.contentView.bounds];
    self.loadingView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    NSStackView *stack = [[NSStackView alloc] init];
    stack.orientation = NSUserInterfaceLayoutOrientationVertical;
    stack.spacing = 22;
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    NSProgressIndicator *spinner = [[NSProgressIndicator alloc] init];
    spinner.style = NSProgressIndicatorStyleSpinning;
    [spinner startAnimation:nil];
    [stack addArrangedSubview:spinner];
    self.loadingLabel = [NSTextField labelWithString:@"Opening your study library…"];
    self.loadingLabel.font = [NSFont systemFontOfSize:18 weight:NSFontWeightMedium];
    [stack addArrangedSubview:self.loadingLabel];
    [self.loadingView addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[
        [stack.centerXAnchor constraintEqualToAnchor:self.loadingView.centerXAnchor],
        [stack.centerYAnchor constraintEqualToAnchor:self.loadingView.centerYAnchor]
    ]];
    [self.window.contentView addSubview:self.loadingView];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
    [self startService];
}

- (void)installPreferenceScript {
    NSData *data = [NSJSONSerialization dataWithJSONObject:self.preferences options:0 error:nil];
    NSString *json = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    NSString *source = [NSString stringWithFormat:
        @"(() => { const saved = %@; const originalSet = Storage.prototype.setItem; "
         "for (const [k, v] of Object.entries(saved)) originalSet.call(localStorage, k, v); "
         "const notify = (key, value) => { if (String(key).startsWith('gw-')) window.webkit.messageHandlers.gospelPreferences.postMessage({key:String(key), value}); }; "
         "Storage.prototype.setItem = function(k,v) { originalSet.call(this,k,v); if(this === localStorage) notify(k,String(v)); }; "
         "const remove = Storage.prototype.removeItem; Storage.prototype.removeItem = function(k) { remove.call(this,k); if(this === localStorage) notify(k,null); }; "
         "const clear = Storage.prototype.clear; Storage.prototype.clear = function() { const keys = Object.keys(this); clear.call(this); if(this === localStorage) keys.forEach(k => notify(k,null)); }; "
         "})();", json];
    if (Flag(@"--disable-decompression")) source = [source stringByAppendingString:@"Object.defineProperty(window, 'DecompressionStream', {value:undefined, configurable:true});"];
    WKUserContentController *controller = self.webView.configuration.userContentController;
    [controller removeAllUserScripts];
    [controller addUserScript:[[WKUserScript alloc] initWithSource:source injectionTime:WKUserScriptInjectionTimeAtDocumentStart forMainFrameOnly:YES]];
}
- (void)userContentController:(WKUserContentController *)controller didReceiveScriptMessage:(WKScriptMessage *)message {
    if (!message.frameInfo.isMainFrame || ![message.body isKindOfClass:NSDictionary.class]) return;
    if ([message.name isEqualToString:@"gospelAppearance"]) {
        NSString *background = message.body[@"background"];
        NSString *skin = message.body[@"skin"];
        if (![skin isKindOfClass:NSString.class] || ![background isKindOfClass:NSString.class] || background.length != 7 || ![background hasPrefix:@"#"]) return;
        NSString *digits = [background substringFromIndex:1];
        if ([digits rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdefABCDEF"] invertedSet]].location != NSNotFound) return;
        unsigned int rgb = 0;
        if (![[NSScanner scannerWithString:digits] scanHexInt:&rgb]) return;
        self.window.appearance = [NSAppearance appearanceNamed:[skin isEqualToString:@"dark"] ? NSAppearanceNameDarkAqua : NSAppearanceNameAqua];
        self.window.titlebarAppearsTransparent = YES;
        self.window.backgroundColor = [NSColor colorWithSRGBRed:((rgb >> 16) & 255) / 255.0 green:((rgb >> 8) & 255) / 255.0 blue:(rgb & 255) / 255.0 alpha:1];
        return;
    }
    NSString *key = message.body[@"key"];
    id value = message.body[@"value"];
    if (![key isKindOfClass:NSString.class] || ![key hasPrefix:@"gw-"]) return;
    if (value == NSNull.null) [self.preferences removeObjectForKey:key];
    else if ([value isKindOfClass:NSString.class]) self.preferences[key] = value;
    else return;
    WriteJSON(self.preferences, self.preferencesPath);
    [self installPreferenceScript];
}

- (void)startService {
    NSString *resources = NSBundle.mainBundle.resourcePath;
    NSString *python = [resources stringByAppendingPathComponent:@"python/bin/python3"];
    NSString *website = [resources stringByAppendingPathComponent:@"website"];
    NSString *library = [self.supportPath stringByAppendingPathComponent:@"library"];
    self.service = [[NSTask alloc] init];
    self.service.executableURL = [NSURL fileURLWithPath:python];
    NSMutableArray *args = [@[@"-I", @"-B", @"-u", [resources stringByAppendingPathComponent:@"desktop_server.py"], @"--website", website, @"--data", library, @"--ready", self.readyPath, @"--parent", [NSString stringWithFormat:@"%d", getpid()], @"--port", Option(@"--port") ?: @"18743"] mutableCopy];
    if (Flag(@"--no-scheduler") || Option(@"--self-test")) [args addObject:@"--no-scheduler"];
    if (Option(@"--self-test")) [args addObject:@"--skip-bundle-merge"];
    if (Option(@"--verification-fixture") && Option(@"--self-test")) [args addObjectsFromArray:@[@"--verification-fixture", Option(@"--verification-fixture")]];
    self.service.arguments = args;
    self.service.currentDirectoryURL = [NSURL fileURLWithPath:self.supportPath];
    NSMutableDictionary *environment = [NSProcessInfo.processInfo.environment mutableCopy];
    environment[@"SSL_CERT_FILE"] = [resources stringByAppendingPathComponent:@"certificates.pem"];
    environment[@"REQUESTS_CA_BUNDLE"] = environment[@"SSL_CERT_FILE"];
    environment[@"PYTHONNOUSERSITE"] = @"1";
    self.service.environment = environment;
    NSString *log = [self.supportPath stringByAppendingPathComponent:@"app-service.log"];
    NSDictionary *attributes = [NSFileManager.defaultManager attributesOfItemAtPath:log error:nil];
    if ([attributes[NSFileSize] unsignedLongLongValue] > 5 * 1024 * 1024) {
        NSString *previous = [log stringByAppendingString:@".previous"];
        [NSFileManager.defaultManager removeItemAtPath:previous error:nil];
        [NSFileManager.defaultManager moveItemAtPath:log toPath:previous error:nil];
    }
    if (![NSFileManager.defaultManager fileExistsAtPath:log]) [NSFileManager.defaultManager createFileAtPath:log contents:nil attributes:nil];
    self.serviceLog = [NSFileHandle fileHandleForWritingAtPath:log];
    [self.serviceLog seekToEndOfFile];
    self.service.standardOutput = self.serviceLog;
    self.service.standardError = self.serviceLog;
    NSError *error = nil;
    if (![self.service launchAndReturnError:&error]) { [self fatal:error.localizedDescription]; return; }
    self.startupTimer = [NSTimer scheduledTimerWithTimeInterval:0.2 target:self selector:@selector(checkServiceReady:) userInfo:nil repeats:YES];
}
- (void)checkServiceReady:(NSTimer *)timer {
    NSDictionary *ready = ReadJSON(self.readyPath);
    if ([ready[@"url"] isKindOfClass:NSString.class]) {
        [timer invalidate];
        self.serviceReady = YES;
        self.baseURL = [NSURL URLWithString:ready[@"url"]];
        [self.webView loadRequest:[NSURLRequest requestWithURL:[self.baseURL URLByAppendingPathComponent:@"study.html"]]];
        self.startupTimer = [NSTimer scheduledTimerWithTimeInterval:2 target:self selector:@selector(watchService:) userInfo:nil repeats:YES];
        return;
    }
    if (!self.service.running || ++self.startupTicks > 3000) {
        [timer invalidate];
        [self fatal:@"The study library could not start. The diagnostic log is in Library/Application Support/Gospel Warrior/app-service.log."];
    }
}
- (void)watchService:(NSTimer *)timer {
    if (!self.terminating && !self.service.running) {
        [timer invalidate];
        [self fatal:@"The local study service stopped. Reopen Gospel Warrior to restart it. Your saved studies and archive are kept in the app's data folder."];
    }
}
- (void)stopService {
    self.terminating = YES;
    [self.startupTimer invalidate];
    if (self.service.running) {
        [self.service terminate];
        for (NSInteger i = 0; i < 30 && self.service.running; i++) [NSThread sleepForTimeInterval:0.1];
        if (self.service.running) kill(self.service.processIdentifier, SIGKILL);
    }
    [self.serviceLog closeFile];
    [NSFileManager.defaultManager removeItemAtPath:self.readyPath error:nil];
}
- (void)applicationWillTerminate:(NSNotification *)notification {
    [self stopService];
    [self.webView.configuration.userContentController removeScriptMessageHandlerForName:@"gospelPreferences"];
    [self.webView.configuration.userContentController removeScriptMessageHandlerForName:@"gospelAppearance"];
    if (self.synchronizationActivity) [NSProcessInfo.processInfo endActivity:self.synchronizationActivity];
}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender { return YES; }
- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)visible {
    [self.window makeKeyAndOrderFront:nil]; return YES;
}

- (void)webView:(WKWebView *)webView didFinishNavigation:(WKNavigation *)navigation {
    self.webView.hidden = NO;
    [self.loadingView removeFromSuperview];
    self.loadingView = nil;
    if (Option(@"--self-test") && !self.testRunning) {
        self.testRunning = YES;
        [NSTimer scheduledTimerWithTimeInterval:0.25 target:self selector:@selector(waitForTestLibrary:) userInfo:nil repeats:YES];
    }
}
- (void)webView:(WKWebView *)webView didFailProvisionalNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    if (error.code != NSURLErrorCancelled) [self fatal:error.localizedDescription];
}
- (void)webViewWebContentProcessDidTerminate:(WKWebView *)webView { [webView reload]; }
- (void)webView:(WKWebView *)webView decidePolicyForNavigationAction:(WKNavigationAction *)action decisionHandler:(void (^)(WKNavigationActionPolicy))decision {
    NSURL *url = action.request.URL;
    BOOL local = [url.host isEqualToString:self.baseURL.host] && [url.port isEqual:self.baseURL.port] && [url.scheme isEqualToString:@"http"];
    if (local) { decision(WKNavigationActionPolicyAllow); return; }
    if ([url.scheme isEqualToString:@"https"] || [url.scheme isEqualToString:@"http"] || [url.scheme isEqualToString:@"mailto"]) [NSWorkspace.sharedWorkspace openURL:url];
    decision(WKNavigationActionPolicyCancel);
}
- (WKWebView *)webView:(WKWebView *)webView createWebViewWithConfiguration:(WKWebViewConfiguration *)configuration forNavigationAction:(WKNavigationAction *)action windowFeatures:(WKWindowFeatures *)features {
    if (action.targetFrame == nil && action.request.URL) [NSWorkspace.sharedWorkspace openURL:action.request.URL];
    return nil;
}

- (void)javascript:(NSString *)source {
    if (self.serviceReady) [self.webView evaluateJavaScript:source completionHandler:nil];
}
- (void)settings:(id)sender { [self javascript:@"openSettings()"] ; }
- (void)updateSettings:(id)sender { [self javascript:@"openSettings('updates')"] ; }
- (void)desk:(id)sender { [self javascript:@"closeSettings(); showView('home')"] ; }
- (void)home:(id)sender { [self javascript:@"closeSettings(); clearAll(); showView('library')"] ; }
- (void)bible:(id)sender { [self javascript:@"closeSettings(); showView('bible')"] ; }
- (void)topics:(id)sender { [self javascript:@"closeSettings(); showView('topics')"] ; }
- (void)search:(id)sender { [self javascript:@"searchStudies()"] ; }
- (void)saved:(id)sender { [self javascript:@"closeSettings(); showView('saved')"] ; }
- (void)refresh:(id)sender { [self javascript:@"refreshArchive().catch(() => {}); void 0;"] ; }
- (void)toggleTheme:(id)sender { [self javascript:@"document.getElementById('readerTheme').click()"] ; }
- (void)largerText:(id)sender { [self javascript:@"document.querySelector('[data-font=up]').click()"] ; }
- (void)smallerText:(id)sender { [self javascript:@"document.querySelector('[data-font=down]').click()"] ; }
- (void)showData:(id)sender { [NSWorkspace.sharedWorkspace openURL:[NSURL fileURLWithPath:self.supportPath]]; }
- (void)about:(id)sender {
    [NSApp orderFrontStandardAboutPanelWithOptions:@{
        NSAboutPanelOptionApplicationName: @"Gospel Warrior",
        NSAboutPanelOptionApplicationVersion: NSBundle.mainBundle.infoDictionary[@"CFBundleShortVersionString"],
        NSAboutPanelOptionVersion: @"Intel Mac · macOS 11 or later",
        @"Copyright": @"Bible Study Library · Read thoughtfully. Follow Jesus faithfully."
    }];
}
- (void)help:(id)sender {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"Your Gospel Warrior study library";
    alert.informativeText = @"Welcome to your study companion. Use the sidebar for your study desk, library, saved studies, Bible index, topics, timeline, and updates.\n\n⌘K — Search studies\n⌘, — Settings\n⌘R — Refresh content in place\n⇧⌘R — Check for new studies\n⌘D — Toggle dark appearance\n⌘1–⌘5 — Navigate the workspace\n\nThe app checks on launch and every 15 minutes while open. New studies load automatically without moving your place in an open study. Settings → Updates contains the automatic-check and automatic-refresh switches.\n\nSaved studies, reading progress, and settings stay on this Mac. All archived studies remain readable offline.";
    [alert beginSheetModalForWindow:self.window completionHandler:nil];
}
- (void)checkUpdates:(id)sender {
    [self javascript:@"requestUpdateCheck(); void 0;"];
}
- (void)updateStatus:(id)sender {
    [self javascript:@"closeSettings(); showView('updates')"];
}

- (void)fatal:(NSString *)message {
    if (Option(@"--self-test")) {
        [self completeTest:@{@"ok": @NO, @"error": message ?: @"Unknown error"}];
        return;
    }
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"Gospel Warrior could not open";
    alert.informativeText = message;
    [alert addButtonWithTitle:@"Close"];
    [alert runModal];
    [NSApp terminate:nil];
}
- (void)waitForTestLibrary:(NSTimer *)timer {
    if (++self.testTicks > 240) {
        [timer invalidate];
        [self completeTest:@{@"ok": @NO, @"error": @"The archive did not load within 60 seconds."}];
        return;
    }
    [self.webView evaluateJavaScript:@"typeof state !== 'undefined' && state.ready && syncState.status !== null && !!document.querySelector('.study-card') && !!document.querySelector('#bookFilter option[value=Genesis]')" completionHandler:^(id result, NSError *error) {
        if (![result boolValue] || !timer.valid) return;
        [timer invalidate];
        NSString *path = [NSBundle.mainBundle.resourcePath stringByAppendingPathComponent:@"selftest.js"];
        NSString *script = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:nil];
        NSString *phase = Option(@"--test-phase") ?: @"1";
        [self.webView evaluateJavaScript:[NSString stringWithFormat:@"window.gospelTestPhase = %@; %@", phase, script] completionHandler:^(id report, NSError *testError) {
            if (testError) { [self completeTest:@{@"ok": @NO, @"error": testError.localizedDescription}]; return; }
            self.testTicks = 0;
            [NSTimer scheduledTimerWithTimeInterval:0.25 target:self selector:@selector(waitForTestReport:) userInfo:nil repeats:YES];
        }];
    }];
}
- (void)waitForTestReport:(NSTimer *)timer {
    if (++self.testTicks > 600) { [timer invalidate]; [self completeTest:@{@"ok": @NO, @"error": @"Native integration tests timed out."}]; return; }
    [self.webView evaluateJavaScript:@"window.gospelTestReport || null" completionHandler:^(id report, NSError *error) {
        if (![report isKindOfClass:NSDictionary.class] || !timer.valid) return;
        [timer invalidate];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), dispatch_get_main_queue(), ^{ [self completeTest:report]; });
    }];
}
- (void)completeTest:(NSDictionary *)report {
    NSString *output = Option(@"--self-test");
    if (!output) return;
    NSMutableDictionary *result = [report mutableCopy];
    result[@"url"] = self.baseURL.absoluteString ?: @"";
    result[@"servicePID"] = @(self.service.processIdentifier);
    result[@"preferences"] = self.preferences ?: @{};
    result[@"macOS"] = NSProcessInfo.processInfo.operatingSystemVersionString;
    result[@"windowAppearance"] = self.window.appearance.name ?: @"system";
    void (^finish)(void) = ^{
        WriteJSON(result, output);
        [NSApp terminate:nil];
    };
    if (!self.webView || !self.serviceReady) { finish(); return; }
    WKSnapshotConfiguration *snapshot = [[WKSnapshotConfiguration alloc] init];
    snapshot.snapshotWidth = @(self.webView.bounds.size.width);
    [self.webView takeSnapshotWithConfiguration:snapshot completionHandler:^(NSImage *image, NSError *error) {
        if (image) {
            NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc] initWithData:image.TIFFRepresentation];
            NSString *screenshot = [[output stringByDeletingPathExtension] stringByAppendingPathExtension:@"png"];
            [[bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}] writeToFile:screenshot atomically:YES];
            result[@"screenshot"] = screenshot;
        }
        finish();
    }];
}
@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
        GospelApp *delegate = [[GospelApp alloc] init];
        NSApp.delegate = delegate;
        [NSApp run];
    }
    return 0;
}
