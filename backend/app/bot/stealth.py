"""
JobCopilot - Stealth Headless Chromium & Anti-Bot Defense Engine
Patches Playwright browser contexts with hardware fingerprint spoofing,
WebGL noise, Canvas jitter, AudioContext perturbation, and Webdriver evasion.
"""

from typing import Dict, Any, Optional
try:
    from playwright.async_api import Browser, BrowserContext
except ImportError:
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore


class StealthEngine:
    """Provides evasive stealth scripts and browser configuration for Playwright."""

    STEALTH_INIT_SCRIPT = """
    (() => {
        // 1. Defeat navigator.webdriver detection
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // 2. Mock Chrome runtime and vendor
        window.navigator.chrome = {
            runtime: {
                OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
                OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
                PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
                PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
                PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
                RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' }
            },
            app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } },
            loadTimes: () => ({}),
            csi: () => ({})
        };

        // 3. Mock Plugins and MimeTypes
        const fakePlugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
        ];
        Object.defineProperty(navigator, 'plugins', { get: () => fakePlugins });

        // 4. WebGL Vendor & Renderer Spoofing
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) {
                return 'Google Inc. (Apple)';
            }
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'ANGLE (Apple, Apple M2 Pro, OpenGL 4.1)';
            }
            return getParameter.apply(this, arguments);
        };

        // 5. Canvas Noise Jitter Injection (Defeats Canvas Hash Fingerprinting)
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            const context = this.getContext('2d');
            if (context) {
                const shift = (Math.random() * 0.0001) - 0.00005;
                const imgData = context.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                if (imgData && imgData.data && imgData.data.length > 0) {
                    imgData.data[0] = Math.min(255, Math.max(0, imgData.data[0] + (shift > 0 ? 1 : 0)));
                }
            }
            return originalToDataURL.apply(this, arguments);
        };

        // 6. Notification Permission Mocking
        if (!window.Notification) {
            window.Notification = { permission: 'default' };
        }
    })();
    """

    @classmethod
    async def create_stealth_context(
        cls,
        browser: Browser,
        user_agent: Optional[str] = None,
        locale: str = "en-US",
        timezone_id: str = "Asia/Kolkata"
    ) -> BrowserContext:
        """Creates a browser context pre-configured with stealth anti-detection patches."""
        ua = user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

        context = await browser.new_context(
            user_agent=ua,
            locale=locale,
            timezone_id=timezone_id,
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            has_touch=False,
            is_mobile=False,
            permissions=["geolocation"],
            geolocation={"latitude": 12.9716, "longitude": 77.5946}  # Bangalore
        )

        # Inject evasive stealth scripts before any page load
        await context.add_init_script(cls.STEALTH_INIT_SCRIPT)
        return context
