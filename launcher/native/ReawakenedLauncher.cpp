// SPDX-License-Identifier: AGPL-3.0-only
// Native GUI wrapper for two existing Reawakened research helpers.
// No Epic credentials, tokens, passwords, game patches, or DLL injection.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <wincrypt.h>
#include <commctrl.h>
#include <securitybaseapi.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <thread>
#include <memory>
#include <atomic>
#include <chrono>
#include <mutex>
#include <algorithm>
#include <array>

#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "advapi32.lib")

namespace {
constexpr wchar_t APP_CLASS[] = L"ReawakenedNativeLauncherWindow";
constexpr wchar_t TITLE[] = L"Dauntless Reawakened | C++ Launcher";
constexpr unsigned WM_LAUNCHER_EVENT = WM_APP + 31;
constexpr unsigned WM_LAUNCHER_FINISH = WM_APP + 32;
constexpr unsigned IDC_ALIAS = 101;
constexpr unsigned IDC_REMEMBER = 102;
constexpr unsigned IDC_CONSENT = 103;
constexpr unsigned IDC_VARIANT = 104;
constexpr unsigned IDC_START = 105;
constexpr unsigned IDC_RESTORE = 106;
constexpr unsigned IDC_FORGET = 107;
constexpr unsigned IDC_LOGS = 108;
constexpr unsigned IDC_STATUS = 109;
constexpr unsigned IDC_CLOSE = 110;
constexpr unsigned IDC_BACKEND_INFO = 111;
constexpr int FINISH_OK = 0, FINISH_RESTORE_REQUIRED = 1, FINISH_FAILED = 2;
constexpr int EVENT_STARTING_SERVER = 1, EVENT_SERVER_READY = 2,
              EVENT_STARTING_GAME = 3, EVENT_FINISHING = 4,
              EVENT_RESTORING = 5;
const std::array<const wchar_t*, 8> PROFILE_VARIANTS = {
    L"without-appearance", L"baseline", L"appearance-only", L"flags-only",
    L"metadata-only", L"without-flags", L"without-metadata", L"full"
};

struct Gui {
    HWND hwnd = nullptr, alias = nullptr, remember = nullptr, consent = nullptr,
         variant = nullptr, start = nullptr, restore = nullptr, forget = nullptr,
         logs = nullptr, status = nullptr, close = nullptr, info = nullptr;
    HFONT font = nullptr, heading = nullptr;
    HBRUSH background = nullptr;
    std::thread worker;
    std::atomic<bool> busy {false};
    std::atomic<bool> restoreNeeded {false};
} g;

struct Child {
    HANDLE process = nullptr;
    HANDLE input = nullptr;
    HANDLE output = nullptr;
    std::thread pump;
    std::atomic<bool> ready {false};
    std::atomic<bool> restored {false};

    ~Child() {
        if (input) CloseHandle(input);
        if (pump.joinable()) {
            if (process && WaitForSingleObject(process, 0) != WAIT_OBJECT_0) {
                // Destruction is only allowed after the process exited.
                // A pending restore keeps the shared_ptr alive until corrected.
                CloseHandle(output);
            }
            pump.join();
        }
        if (output) CloseHandle(output);
        if (process) CloseHandle(process);
    }
};
std::shared_ptr<Child> g_server;
std::mutex g_children_mutex;

std::wstring exeDirectory() {
    std::vector<wchar_t> buffer(32768, L'\0');
    DWORD n = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (!n || n >= buffer.size()) return L"";
    return std::filesystem::path(std::wstring(buffer.data(), n)).parent_path().wstring();
}
std::wstring localAppData() {
    DWORD len = GetEnvironmentVariableW(L"LOCALAPPDATA", nullptr, 0);
    if (len < 2 || len > 32768) return L"";
    std::wstring out(len, L'\0');
    DWORD got = GetEnvironmentVariableW(L"LOCALAPPDATA", out.data(), len);
    if (!got || got >= len) return L"";
    out.resize(got);
    return out;
}
std::wstring profileDirectory() {
    return (std::filesystem::path(localAppData()) / L"DauntlessReawakenedLauncher").wstring();
}
std::wstring settingsFile() {
    return (std::filesystem::path(profileDirectory()) / L"settings.dpapi").wstring();
}
std::wstring reportJournal() {
    return (std::filesystem::path(localAppData()) / L"DauntlessReawakenedMapTest" /
            L"active" / L"journal.json").wstring();
}
std::wstring quote(const std::wstring& s) {
    // Arguments here are either fixed flags, allowlisted variants or known full paths.
    // Windows command-line escape for arbitrary quotes/backslashes in future paths.
    std::wstring out = L"\"";
    unsigned slashes = 0;
    for (wchar_t ch : s) {
        if (ch == L'\\') { ++slashes; continue; }
        if (ch == L'\"') {
            out.append(slashes * 2 + 1, L'\\');
            out.push_back(ch);
        } else {
            out.append(slashes, L'\\');
            out.push_back(ch);
        }
        slashes = 0;
    }
    out.append(slashes * 2, L'\\');
    return out + L"\"";
}
std::wstring commandFor(const std::wstring& exe, const std::vector<std::wstring>& args) {
    std::wstring out = quote(exe);
    for (const auto& a : args) out += L" " + quote(a);
    return out;
}
bool variantAllowed(const std::wstring& value) {
    for (auto* name : PROFILE_VARIANTS) if (value == name) return true;
    return false;
}
bool fileIsRegular(const std::wstring& path) {
    DWORD attrs = GetFileAttributesW(path.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES &&
           !(attrs & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT));
}
bool elevated() {
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) return false;
    TOKEN_ELEVATION elevation {};
    DWORD size = 0;
    BOOL ok = GetTokenInformation(token, TokenElevation, &elevation, sizeof(elevation), &size);
    CloseHandle(token);
    return ok && elevation.TokenIsElevated != 0;
}
void signalGui(int code) {
    if (g.hwnd) PostMessageW(g.hwnd, WM_LAUNCHER_EVENT, static_cast<WPARAM>(code), 0);
}
void doneGui(int result) {
    if (g.hwnd) PostMessageW(g.hwnd, WM_LAUNCHER_FINISH, static_cast<WPARAM>(result), 0);
}

std::string asUtf8(const std::wstring& wide) {
    if (wide.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.data(),
                                static_cast<int>(wide.size()), nullptr, 0, nullptr, nullptr);
    if (n <= 0 || n > 16384) return {};
    std::string out(static_cast<size_t>(n), '\0');
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide.data(),
        static_cast<int>(wide.size()), out.data(), n, nullptr, nullptr)) return {};
    return out;
}
std::wstring fromUtf8(const std::string& value) {
    if (value.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                static_cast<int>(value.size()), nullptr, 0);
    if (n <= 0 || n > 2048) return {};
    std::wstring out(static_cast<size_t>(n), L'\0');
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), out.data(), n)) return {};
    return out;
}
std::wstring validAlias(std::wstring v) {
    if (v.size() > 80) v.resize(80);
    for (wchar_t& c : v) if (c < L' ' || c == L'\x7f') c = L' ';
    return v;
}
// DPAPI ties this data to the current Windows user. Never store actual Epic secrets.
const BYTE ENTROPY[] = "Reawakened-display-only-v1";
bool protectString(const std::string& plain, std::vector<BYTE>& cipher) {
    DATA_BLOB in {static_cast<DWORD>(plain.size()),
                  reinterpret_cast<BYTE*>(const_cast<char*>(plain.data()))};
    DATA_BLOB extra {static_cast<DWORD>(sizeof(ENTROPY)), const_cast<BYTE*>(ENTROPY)};
    DATA_BLOB out {};
    if (!CryptProtectData(&in, L"Reawakened display preferences", &extra,
                          nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &out)) return false;
    cipher.assign(out.pbData, out.pbData + out.cbData);
    LocalFree(out.pbData);
    return true;
}
bool unprotectString(const std::vector<BYTE>& cipher, std::string& plain) {
    if (cipher.empty() || cipher.size() > 16384) return false;
    DATA_BLOB in {static_cast<DWORD>(cipher.size()), const_cast<BYTE*>(cipher.data())};
    DATA_BLOB extra {static_cast<DWORD>(sizeof(ENTROPY)), const_cast<BYTE*>(ENTROPY)};
    DATA_BLOB out {};
    if (!CryptUnprotectData(&in, nullptr, &extra, nullptr, nullptr,
                           CRYPTPROTECT_UI_FORBIDDEN, &out)) return false;
    if (out.cbData > 4096) { SecureZeroMemory(out.pbData, out.cbData); LocalFree(out.pbData); return false; }
    plain.assign(reinterpret_cast<const char*>(out.pbData), out.cbData);
    SecureZeroMemory(out.pbData, out.cbData);
    LocalFree(out.pbData);
    return true;
}
struct Preferences { std::wstring alias, variant = L"without-appearance"; bool remembered=false; };
Preferences readPreferences() {
    Preferences settings;
    auto path = settingsFile();
    if (path.empty() || !fileIsRegular(path)) return settings;
    HANDLE f = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return settings;
    LARGE_INTEGER size {};
    if (!GetFileSizeEx(f, &size) || size.QuadPart < 1 || size.QuadPart > 16384) { CloseHandle(f); return settings; }
    std::vector<BYTE> cipher(static_cast<size_t>(size.QuadPart));
    DWORD got = 0;
    BOOL ok = ReadFile(f, cipher.data(), static_cast<DWORD>(cipher.size()), &got, nullptr);
    CloseHandle(f);
    if (!ok || got != cipher.size()) return settings;
    std::string text;
    if (!unprotectString(cipher, text)) return settings;
    if (text.rfind("RWL1\n", 0) != 0) return settings;
    const size_t split = text.find('\n', 5);
    if (split == std::string::npos || split > 50) return settings;
    auto variant = fromUtf8(text.substr(5, split - 5));
    auto alias = fromUtf8(text.substr(split+1));
    if (!variantAllowed(variant) || alias.size() > 80) return settings;
    settings.variant = variant;
    settings.alias = validAlias(alias);
    settings.remembered = true;
    return settings;
}
bool savePreferences(const Preferences& settings) {
    if (!settings.remembered) return DeleteFileW(settingsFile().c_str()) || GetLastError() == ERROR_FILE_NOT_FOUND;
    if (!variantAllowed(settings.variant) || settings.alias.size() > 80) return false;
    const std::string plain = "RWL1\n" + asUtf8(settings.variant) + "\n" + asUtf8(validAlias(settings.alias));
    std::vector<BYTE> cipher;
    if (!protectString(plain, cipher)) return false;
    auto dir = profileDirectory();
    if (dir.empty()) return false;
    if (!CreateDirectoryW(dir.c_str(), nullptr) && GetLastError() != ERROR_ALREADY_EXISTS) return false;
    DWORD attributes = GetFileAttributesW(dir.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) return false;
    auto filename = settingsFile();
    if (GetFileAttributesW(filename.c_str()) != INVALID_FILE_ATTRIBUTES && !fileIsRegular(filename)) return false;
    HANDLE f = CreateFileW(filename.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(f, cipher.data(), static_cast<DWORD>(cipher.size()), &written, nullptr);
    if (ok) FlushFileBuffers(f);
    CloseHandle(f);
    return ok && written == cipher.size();
}

bool journalRestoredOrAbsent() {
    auto path = reportJournal();
    if (path.empty() || !fileIsRegular(path)) {
        // Missing journal is safe only if the file really doesn't exist.
        return GetFileAttributesW(path.c_str()) == INVALID_FILE_ATTRIBUTES;
    }
    std::ifstream stream(std::filesystem::path(path), std::ios::binary);
    if (!stream) return false;
    std::string text(65536, '\0');
    stream.read(text.data(), static_cast<std::streamsize>(text.size()));
    auto count = stream.gcount();
    if (!stream.eof()) return false;
    text.resize(static_cast<size_t>(count));
    return text.find("\"restored\": true") != std::string::npos ||
           text.find("\"restored\":true") != std::string::npos;
}

void lineFromChild(const std::shared_ptr<Child>& child, const std::string& line) {
    // Match only hard-coded sanitized progress phrases. Raw lines are discarded.
    if (line.find("CLIENT PORTS READY") != std::string::npos) {
        child->ready = true;
        signalGui(EVENT_SERVER_READY);
    }
    if (line.find("Original configuration, game CA and hosts entries restored.") != std::string::npos ||
        line.find("Map preview changes restored.") != std::string::npos) {
        child->restored = true;
    }
}
std::shared_ptr<Child> launch(const std::wstring& exe, const std::vector<std::wstring>& args) {
    if (!fileIsRegular(exe)) return nullptr;
    SECURITY_ATTRIBUTES security {sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    HANDLE childIn = nullptr, parentIn = nullptr, parentOut = nullptr, childOut = nullptr;
    if (!CreatePipe(&childIn, &parentIn, &security, 0)) return nullptr;
    if (!SetHandleInformation(parentIn, HANDLE_FLAG_INHERIT, 0) ||
        !CreatePipe(&parentOut, &childOut, &security, 0) ||
        !SetHandleInformation(parentOut, HANDLE_FLAG_INHERIT, 0)) {
        CloseHandle(childIn); CloseHandle(parentIn);
        if (parentOut) CloseHandle(parentOut);
        if (childOut) CloseHandle(childOut);
        return nullptr;
    }
    STARTUPINFOW si {};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = childIn;
    si.hStdOutput = childOut;
    si.hStdError = childOut;
    PROCESS_INFORMATION pi {};
    auto command = commandFor(exe, args);
    std::vector<wchar_t> mutableCommand(command.begin(), command.end());
    mutableCommand.push_back(L'\0');
    std::wstring working = std::filesystem::path(exe).parent_path().wstring();
    BOOL ok = CreateProcessW(exe.c_str(), mutableCommand.data(), nullptr, nullptr,
                             TRUE, CREATE_NO_WINDOW, nullptr, working.c_str(), &si, &pi);
    CloseHandle(childIn);
    CloseHandle(childOut);
    if (!ok) { CloseHandle(parentIn); CloseHandle(parentOut); return nullptr; }
    CloseHandle(pi.hThread);
    auto child = std::make_shared<Child>();
    child->process = pi.hProcess;
    child->input = parentIn;
    child->output = parentOut;
    child->pump = std::thread([child]() {
        std::string line;
        bool oversize = false;
        char buffer[4096];
        DWORD read = 0;
        while (ReadFile(child->output, buffer, sizeof(buffer), &read, nullptr) && read) {
            for (DWORD i = 0; i < read; ++i) {
                char c = buffer[i];
                if (c == '\r' || c == '\n') {
                    if (!oversize) lineFromChild(child, line);
                    line.clear(); oversize = false;
                } else if (!oversize) {
                    if (line.size() < 1024) line.push_back(c);
                    else { line.clear(); oversize = true; }
                }
            }
        }
        if (!oversize) lineFromChild(child, line);
    });
    return child;
}
bool sendCommand(const std::shared_ptr<Child>& child, const char* command, DWORD length) {
    if (!child || !child->input) return false;
    DWORD written=0;
    BOOL ok=WriteFile(child->input, command, length, &written, nullptr);
    return ok && written==length;
}
void closeInput(const std::shared_ptr<Child>& child) {
    if (child && child->input) { CloseHandle(child->input); child->input = nullptr; }
}
bool stopServer() {
    std::shared_ptr<Child> server;
    { std::lock_guard<std::mutex> lock(g_children_mutex); server = g_server; }
    if (!server) return true;
    if (WaitForSingleObject(server->process, 0) == WAIT_TIMEOUT) {
        sendCommand(server, "STOP\n", 5);
        closeInput(server);
        if (WaitForSingleObject(server->process, 12000) != WAIT_OBJECT_0) return false;
    }
    if (server->pump.joinable()) server->pump.join();
    { std::lock_guard<std::mutex> lock(g_children_mutex); g_server.reset(); }
    return true;
}
void startRun(std::wstring variant) {
    signalGui(EVENT_STARTING_SERVER);
    std::wstring dir=exeDirectory();
    if (dir.empty()) { doneGui(FINISH_FAILED); return; }
    auto server = launch((std::filesystem::path(dir)/L"Reawakened-Local-Server.exe").wstring(),
           {L"--client-ports",L"--diagnostic",L"--presence",L"--mystic-profile",
            L"--profile-variant",variant,L"--launcher-control"});
    if (!server) { doneGui(FINISH_FAILED); return; }
    { std::lock_guard<std::mutex> lock(g_children_mutex); g_server=server; }
    bool ready=false;
    for (int i=0;i<300;i++) {
        if (server->ready) { ready=true; break; }
        if (WaitForSingleObject(server->process,0)!=WAIT_TIMEOUT) break;
        Sleep(100);
    }
    if (!ready) { stopServer(); doneGui(FINISH_FAILED); return; }
    signalGui(EVENT_STARTING_GAME);
    auto preview=launch((std::filesystem::path(dir)/L"Reawakened-Ramsgate-Preview.exe").wstring(),
       {L"--run",L"--normal-login",L"--external-server",L"--trace-client",L"--seconds",L"600"});
    if (!preview) { stopServer(); doneGui(FINISH_FAILED); return; }
    if (!sendCommand(preview,"MAP\n",4)) {
        closeInput(preview);
        WaitForSingleObject(preview->process,15000);
        if (preview->pump.joinable()) preview->pump.join();
        if (journalRestoredOrAbsent()) stopServer();
        doneGui(FINISH_FAILED);
        return;
    }
    closeInput(preview);
    // The Python helper owns and monitors the stock game process. Do not kill it
    // from this native GUI, or the journal's finally/restore could be bypassed.
    WaitForSingleObject(preview->process, INFINITE);
    if (preview->pump.joinable()) preview->pump.join();
    DWORD exitCode=1;
    GetExitCodeProcess(preview->process,&exitCode);
    signalGui(EVENT_FINISHING);
    if ((preview->restored || journalRestoredOrAbsent()) && stopServer()) {
        doneGui(exitCode == 0 ? FINISH_OK : FINISH_FAILED);
    } else doneGui(FINISH_RESTORE_REQUIRED);
}
void restoreRun() {
    signalGui(EVENT_RESTORING);
    const auto exe=(std::filesystem::path(exeDirectory())/L"Reawakened-Ramsgate-Preview.exe").wstring();
    auto preview=launch(exe,{L"--restore"});
    if (!preview) { doneGui(FINISH_RESTORE_REQUIRED); return; }
    closeInput(preview);
    WaitForSingleObject(preview->process, INFINITE);
    if (preview->pump.joinable()) preview->pump.join();
    DWORD code=1; GetExitCodeProcess(preview->process,&code);
    if (code == 0 && journalRestoredOrAbsent() && stopServer()) doneGui(FINISH_OK);
    else doneGui(FINISH_RESTORE_REQUIRED);
}

HWND control(const wchar_t* cls, const wchar_t* label, DWORD style,
             int x, int y, int w, int h, int id=0, DWORD ex=0) {
    HWND item=CreateWindowExW(ex,cls,label,WS_CHILD|WS_VISIBLE|style,
                              x,y,w,h,g.hwnd,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                              GetModuleHandleW(nullptr),nullptr);
    if (item && g.font) SendMessageW(item,WM_SETFONT,reinterpret_cast<WPARAM>(g.font),TRUE);
    return item;
}
void updateButtons() {
    bool busy=g.busy.load();
    EnableWindow(g.start,!busy && !g.restoreNeeded.load());
    EnableWindow(g.restore,!busy);
    EnableWindow(g.variant,!busy);
    EnableWindow(g.alias,!busy);
    EnableWindow(g.remember,!busy);
    EnableWindow(g.consent,!busy);
    EnableWindow(g.forget,!busy);
}
void setStatus(const wchar_t* value) {
    SetWindowTextW(g.status,value);
}
std::wstring currentVariant() {
    wchar_t buf[64]{};
    int i=static_cast<int>(SendMessageW(g.variant,CB_GETCURSEL,0,0));
    if (i<0 || i>=static_cast<int>(PROFILE_VARIANTS.size())) return {};
    SendMessageW(g.variant,CB_GETLBTEXT,static_cast<WPARAM>(i),reinterpret_cast<LPARAM>(buf));
    return buf;
}
void selectVariant(const std::wstring& s) {
    for (size_t i=0;i<PROFILE_VARIANTS.size();i++) if (s==PROFILE_VARIANTS[i]) {
        SendMessageW(g.variant,CB_SETCURSEL,static_cast<WPARAM>(i),0);return;
    }
    SendMessageW(g.variant,CB_SETCURSEL,0,0);
}
void finishUi(int status) {
    if (g.worker.joinable()) g.worker.join();
    g.busy=false;
    if (status == FINISH_RESTORE_REQUIRED) {
        g.restoreNeeded=true;
        setStatus(L"Gendannelse ikke bekræftet. Luk spillet og klik Gendan.");
    } else if(status == FINISH_OK) {
        g.restoreNeeded=false;
        setStatus(L"Spil lukket; konfiguration gendannet og server stoppet.");
    } else {
        g.restoreNeeded=!journalRestoredOrAbsent();
        setStatus(L"Testen kunne ikke fuldføres. Kontrollér logs og gendannelse.");
    }
    updateButtons();
}
void elevateSelf() {
    wchar_t full[MAX_PATH]{};
    if (!GetModuleFileNameW(nullptr,full,MAX_PATH)) return;
    HINSTANCE h=ShellExecuteW(g.hwnd,L"runas",full,nullptr,exeDirectory().c_str(),SW_SHOWNORMAL);
    if (reinterpret_cast<INT_PTR>(h)>32) DestroyWindow(g.hwnd);
    else MessageBoxW(g.hwnd,L"Administratoradgang blev ikke givet.",TITLE,MB_OK|MB_ICONWARNING);
}
void beginRun() {
    if (g.busy || g.restoreNeeded) return;
    if (!elevated()) {
        MessageBoxW(g.hwnd,L"Testen ændrer midlertidigt hosts-filen og spillets CA.\n"
            L"Launcheren genstartes derfor som administrator. Afkryds samtykket igen.",TITLE,
            MB_OK|MB_ICONINFORMATION);
        elevateSelf();return;
    }
    if (SendMessageW(g.consent,BM_GETCHECK,0,0)!=BST_CHECKED) {
        MessageBoxW(g.hwnd,L"Bekræft først de midlertidige ændringer. De gendannes, når spillet lukkes.",
                    TITLE,MB_OK|MB_ICONWARNING);return;
    }
    if (!journalRestoredOrAbsent()) {
        g.restoreNeeded=true;
        setStatus(L"Et tidligere forsøg mangler gendannelse. Klik Gendan først.");
        updateButtons();return;
    }
    auto variant=currentVariant();
    if (!variantAllowed(variant)) return;
    wchar_t alias[128]{};
    GetWindowTextW(g.alias,alias,static_cast<int>(std::size(alias)));
    Preferences pref {validAlias(alias),variant,
                      SendMessageW(g.remember,BM_GETCHECK,0,0)==BST_CHECKED};
    if (!savePreferences(pref)) {
        MessageBoxW(g.hwnd,L"Kunne ikke gemme/slette det lokale kontonavn sikkert.\n"
                    L"Testen startes ikke, før dette er løst.",TITLE,MB_OK|MB_ICONERROR);
        return;
    }
    g.busy=true;
    updateButtons();
    g.worker=std::thread([variant]() {startRun(variant);});
}
void beginRestore() {
    if(g.busy)return;
    if (!elevated()) {elevateSelf();return;}
    if(g.worker.joinable())g.worker.join();
    g.busy=true;updateButtons();
    g.worker=std::thread([](){restoreRun();});
}
void forgetName() {
    if(g.busy)return;
    DeleteFileW(settingsFile().c_str());
    SetWindowTextW(g.alias,L"");
    SendMessageW(g.remember,BM_SETCHECK,BST_UNCHECKED,0);
    setStatus(L"Gemt kontonavn slettet (ingen Epic-legitimationsoplysninger var gemt).");
}
void createInterface() {
    g.background=CreateSolidBrush(RGB(20,26,39));
    g.font=CreateFontW(-19,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
                        OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,
                        DEFAULT_PITCH,L"Segoe UI");
    g.heading=CreateFontW(-30,0,0,0,FW_BOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,
                           OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,
                           DEFAULT_PITCH,L"Segoe UI");
    HWND title=control(L"STATIC",L"DAUNTLESS REAWAKENED",SS_LEFT,26,16,700,45);
    SendMessageW(title,WM_SETFONT,reinterpret_cast<WPARAM>(g.heading),TRUE);
    control(L"STATIC",L"Windows C++ Launcher  •  Original 2.1.1 klient  •  Lokal backend",SS_LEFT,
            28,65,700,27);
    control(L"STATIC",L"Kontonavn (valgfrit – kun til visning, ikke Epic-login)",SS_LEFT,
            28,112,630,24);
    g.alias=control(L"EDIT",L"",WS_BORDER|ES_AUTOHSCROLL|WS_TABSTOP,
            28,141,470,32,IDC_ALIAS,WS_EX_CLIENTEDGE);
    g.forget=control(L"BUTTON",L"Glem navn",BS_PUSHBUTTON|WS_TABSTOP,
            508,140,160,34,IDC_FORGET);
    g.remember=control(L"BUTTON",L"Husk navn med Windows-kryptering (DPAPI)",
            BS_AUTOCHECKBOX|WS_TABSTOP,28,183,630,30,IDC_REMEMBER);
    control(L"STATIC",L"Karakterprofil til næste test",SS_LEFT,28,233,460,25);
    g.variant=control(L"COMBOBOX",L"",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,
            28,265,365,230,IDC_VARIANT);
    for(auto* name: PROFILE_VARIANTS) SendMessageW(g.variant,CB_ADDSTRING,0,
                                                     reinterpret_cast<LPARAM>(name));
    control(L"STATIC",L"Epic-login foregår i Epics egen browser. Vi gemmer hverken Epic-adgangskode eller tokens.",
            SS_LEFT,28,310,695,48);
    g.consent=control(L"BUTTON",L"Jeg accepterer midlertidige ændringer af hosts, spil-CA og konfiguration",
            BS_AUTOCHECKBOX|WS_TABSTOP,28,374,715,29,IDC_CONSENT);
    g.start=control(L"BUTTON",L"START SPILLET",BS_DEFPUSHBUTTON|WS_TABSTOP,
            28,420,220,48,IDC_START);
    g.restore=control(L"BUTTON",L"Gendan",BS_PUSHBUTTON|WS_TABSTOP,
            260,420,132,48,IDC_RESTORE);
    g.logs=control(L"BUTTON",L"Åbn logs",BS_PUSHBUTTON|WS_TABSTOP,
            405,420,134,48,IDC_LOGS);
    g.close=control(L"BUTTON",L"Luk",BS_PUSHBUTTON|WS_TABSTOP,
            554,420,114,48,IDC_CLOSE);
    g.status=control(L"STATIC",L"Klar til lokal test. Spilbar Ramsgate-server findes endnu ikke.",
            SS_LEFT,28,493,710,36,IDC_STATUS);
    auto pref=readPreferences();
    SetWindowTextW(g.alias,pref.alias.c_str());
    selectVariant(pref.variant);
    SendMessageW(g.remember,BM_SETCHECK,pref.remember?BST_CHECKED:BST_UNCHECKED,0);
    g.restoreNeeded=!journalRestoredOrAbsent();
    if(g.restoreNeeded) setStatus(L"Tidligere test mangler gendannelse. Luk spillet og klik Gendan.");
    updateButtons();
}
LRESULT CALLBACK windowProcedure(HWND hwnd,UINT message,WPARAM wparam,LPARAM lparam) {
    switch(message) {
      case WM_CREATE: g.hwnd=hwnd;createInterface();return 0;
      case WM_ERASEBKGND: {
          RECT rc{}; GetClientRect(hwnd, &rc);
          FillRect(reinterpret_cast<HDC>(wparam), &rc, g.background);
          return 1;
      }
      case WM_CTLCOLORSTATIC: {
          HDC dc=reinterpret_cast<HDC>(wparam);
          SetTextColor(dc,RGB(227,237,251));
          SetBkColor(dc,RGB(20,26,39));
          return reinterpret_cast<LRESULT>(g.background);
      }
      case WM_COMMAND:
        if(HIWORD(wparam)==BN_CLICKED) switch(LOWORD(wparam)) {
          case IDC_START:beginRun();break;
          case IDC_RESTORE:beginRestore();break;
          case IDC_FORGET:forgetName();break;
          case IDC_LOGS: {
             auto p=(std::filesystem::path(localAppData()) /L"DauntlessReawakenedServer"/L"logs").wstring();
             ShellExecuteW(hwnd,L"open",p.c_str(),nullptr,nullptr,SW_SHOWNORMAL);
             break;
          }
          case IDC_CLOSE:PostMessageW(hwnd,WM_CLOSE,0,0);break;
        }
        return 0;
      case WM_LAUNCHER_EVENT:
        switch(static_cast<int>(wparam)) {
          case EVENT_STARTING_SERVER:setStatus(L"Starter den lokale 2.1.1 API-server …");break;
          case EVENT_SERVER_READY:setStatus(L"Lokal server klar. Forbereder original Dauntless-klient …");break;
          case EVENT_STARTING_GAME:setStatus(L"Dauntless kører. Epic-login foregår i browseren. Luk spillet normalt bagefter.");break;
          case EVENT_FINISHING:setStatus(L"Spillet afsluttet. Kontrollerer gendannelse og stopper serveren …");break;
          case EVENT_RESTORING:setStatus(L"Forsøger at gendanne original hosts, spil-CA og konfiguration …");break;
        }
        return 0;
      case WM_LAUNCHER_FINISH:finishUi(static_cast<int>(wparam));return 0;
      case WM_CLOSE:
        if(g.busy || g.restoreNeeded) {
            MessageBoxW(hwnd,L"Luk først Dauntless normalt og vent på gendannelsen.\n"
                    L"Hvis gendannelsen fejlede, brug knappen Gendan med spillet lukket.\n"
                    L"Launcheren lukker ikke automatisk spillet.",TITLE,MB_OK|MB_ICONWARNING);
            return 0;
        }
        DestroyWindow(hwnd);return 0;
      case WM_DESTROY:
        if(g.worker.joinable())g.worker.join();
        if(g.background)DeleteObject(g.background);
        if(g.font)DeleteObject(g.font);
        if(g.heading)DeleteObject(g.heading);
        g.hwnd=nullptr;
        PostQuitMessage(0);return 0;
    }
    return DefWindowProcW(hwnd,message,wparam,lparam);
}
int runSelfTest() {
    std::string output;
    std::vector<BYTE> ciphertext;
    if (!protectString("RWL1\nwithout-appearance\nTestSlayer",ciphertext) ||
        !unprotectString(ciphertext,output) ||
        output!="RWL1\nwithout-appearance\nTestSlayer")return 1;
    if (ciphertext.size()<30 || std::search(ciphertext.begin(),ciphertext.end(),
         output.begin(),output.end())!=ciphertext.end()) return 2;
    if (!variantAllowed(L"without-appearance") || variantAllowed(L"malicious"))return 3;
    auto cmd=commandFor(L"C:\\Program Files\\Example\\launcher helper.exe",{
        L"--mystic-profile",L"--profile-variant",L"without-appearance"});
    if(cmd.find(L"\"C:\\Program Files\\Example\\launcher helper.exe\"")==std::wstring::npos ||
       cmd.find(L"--profile-variant")==std::wstring::npos ||
       cmd.find(L"AUTH_PASSWORD")!=std::wstring::npos)return 4;
    if(fromUtf8(asUtf8(L"Lokalt navn"))!=L"Lokalt navn")return 5;
    return 0;
}
} // anonymous namespace

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int show) {
    int argc=0;
    LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    bool selfTest=false;
    for(int i=1;i<argc;i++)if(std::wstring(argv[i])==L"--self-test")selfTest=true;
    if(argv)LocalFree(argv);
    if(selfTest)return runSelfTest();
    SetProcessDPIAware();
    INITCOMMONCONTROLSEX ctl{sizeof(ctl),ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&ctl);
    WNDCLASSEXW wc{};
    wc.cbSize=sizeof(wc);wc.lpfnWndProc=windowProcedure;wc.hInstance=instance;
    wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
    wc.hbrBackground=nullptr;
    wc.lpszClassName=APP_CLASS;
    if(!RegisterClassExW(&wc))return 1;
    HWND window=CreateWindowExW(0,APP_CLASS,TITLE,WS_OVERLAPPEDWINDOW & ~WS_MAXIMIZEBOX & ~WS_THICKFRAME,
                CW_USEDEFAULT,CW_USEDEFAULT,764,578,nullptr,nullptr,instance,nullptr);
    if(!window)return 2;
    ShowWindow(window,show);UpdateWindow(window);
    MSG message{};
    while(GetMessageW(&message,nullptr,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}
    return static_cast<int>(message.wParam);
}
