import { useState, useCallback, useEffect } from "react";
import { Header } from "./components/layout/Header";
import { BottomBar } from "./components/layout/BottomBar";
import { Footer } from "./components/layout/Footer";
import { RobotScene } from "./components/viewer3d/RobotScene";
import { BlocklyEditor } from "./components/blockly/BlocklyEditor";
import { DocsPanel } from "./components/docs/DocsPanel";
import { useRobotStore } from "./stores/robotStore";
import { api } from "./services/api";

export default function App() {
  const [splitPercent, setSplitPercent] = useState(65);
  const [isDragging, setIsDragging] = useState(false);
  const [showWarning, setShowWarning] = useState(true);
  const [activeTab, setActiveTab] = useState<"control" | "docs">("control");
  const [blocklyVisible, setBlocklyVisible] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [loginError, setLoginError] = useState("");
  const { status, addLog } = useRobotStore();

  useEffect(() => {
    const token = api.loadToken();
    if (token) {
      api.getStatus().then((res) => {
        if (res.connected) {
          setShowLogin(false);
          setShowWarning(true);
          addLog("Сессия восстановлена", "ok");
        } else {
          setShowLogin(true);
        }
      }).catch(() => {
        setShowLogin(true);
      });
    } else {
      setShowLogin(true);
    }
  }, []);

  useEffect(() => {
    if (status === "connected") {
      const timer = setTimeout(() => setShowWarning(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [status]);

  const handleMouseDown = useCallback(() => setIsDragging(true), []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      const container = e.currentTarget as HTMLElement;
      const rect = container.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.max(30, Math.min(80, pct)));
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

  if (showLogin) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-200 p-8">
        <div className="max-w-md w-full bg-gray-100 rounded-lg shadow-xl p-6 border border-gray-300">
          <div className="text-center mb-4">
            <span className="text-4xl">🤖</span>
          </div>
          <h2 className="text-xl font-bold text-black mb-2 text-center">
            ST3215 Robot Control
          </h2>
          <p className="text-black text-sm mb-4 text-center">
            Введите логин и пароль для доступа
          </p>
          {loginError && (
            <div className="bg-red-200 border border-red-500 text-red-800 px-3 py-2 rounded mb-3 text-sm font-medium">
              {loginError}
            </div>
          )}
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-black font-medium mb-1">Логин</label>
              <input
                id="usernameInput"
                className="w-full border border-gray-400 rounded px-3 py-2 bg-white text-black"
                placeholder="admin"
                defaultValue="admin"
              />
            </div>
            <div>
              <label className="block text-sm text-black font-medium mb-1">Пароль</label>
              <input
                id="passwordInput"
                type="password"
                className="w-full border border-gray-400 rounded px-3 py-2 bg-white text-black"
                placeholder="admin"
                defaultValue="admin"
              />
            </div>
            <button
              onClick={async () => {
                const usernameInput = document.getElementById("usernameInput") as HTMLInputElement;
                const passwordInput = document.getElementById("passwordInput") as HTMLInputElement;
                const username = usernameInput?.value || "admin";
                const password = passwordInput?.value || "admin";
                try {
                  await api.login(username, password);
                  setShowLogin(false);
                  setShowWarning(true);
                  addLog("Авторизован: " + username, "ok");
                } catch (e) {
                  setLoginError(e instanceof Error ? e.message : "Ошибка авторизации");
                }
              }}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
            >
              Войти
            </button>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-gray-100 text-black">или</span>
              </div>
            </div>
            <button
              onClick={async () => {
                const secret = prompt("Введите секретный ключ:");
                if (secret) {
                  try {
                    api.setLimitedSecret(secret);
                    setShowLogin(false);
                    setShowWarning(true);
                    addLog("Ограниченный режим", "warn");
                  } catch {
                    setLoginError("Неверный ключ");
                  }
                }
              }}
              className="w-full bg-gray-300 hover:bg-gray-400 text-black px-6 py-2 rounded-lg font-medium border border-gray-400"
            >
              Ограниченный доступ (ключ)
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (showWarning && status === "disconnected") {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-100 p-8">
        <div className="max-w-lg text-center space-y-6">
          <div className="bg-amber-50 border-2 border-amber-400 rounded-lg p-6">
            <h2 className="text-xl font-bold text-amber-800 mb-3">
              ⚠️ Внимание
            </h2>
            <p className="text-amber-900 text-sm space-y-2">
              Это устройство управляет реальным роботом с сервоприводами.
              Неправильные команды могут привести к:
            </p>
            <ul className="text-left text-amber-800 text-sm mt-3 ml-4 list-disc">
              <li>Поломке сервоприводов</li>
              <li>Механическому повреждению робота</li>
              <li>Травмам при касании движущихся частей</li>
            </ul>
            <p className="text-amber-900 text-sm mt-3 font-semibold">
              Убедитесь, что робот находится в безопасном положении перед подключением!
            </p>
          </div>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => setShowWarning(false)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
            >
              Продолжить
            </button>
            <button
              onClick={() => {
                setShowLogin(false);
                setShowWarning(false);
                setActiveTab("docs");
              }}
              className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-6 py-2 rounded-lg font-medium"
            >
              Документация
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100 text-gray-800">
      {/* Tabs */}
      <div className="flex border-b border-gray-300 bg-white px-4">
        <button
          onClick={() => setActiveTab("control")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "control"
              ? "border-emerald-500 text-emerald-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Управление
        </button>
        <button
          onClick={() => setActiveTab("docs")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "docs"
              ? "border-emerald-500 text-emerald-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Документация
        </button>
      </div>

      {activeTab === "control" ? (
        <>
          <Header onToggleBlockly={() => setBlocklyVisible(!blocklyVisible)} blocklyVisible={blocklyVisible} />

          <div
            className="flex flex-1 min-h-0 overflow-hidden"
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <div
              style={{ width: blocklyVisible ? `${splitPercent}%` : "100%" }}
              className="h-full overflow-hidden"
            >
              <RobotScene />
            </div>

            {blocklyVisible && (
              <>
                <div
                  onMouseDown={handleMouseDown}
                  className={`w-1 cursor-col-resize hover:bg-emerald-500/50 transition-colors shrink-0 ${
                    isDragging ? "bg-emerald-500/50" : "bg-gray-300"
                  }`}
                />

                <div
                  style={{ width: `${100 - splitPercent}%` }}
                  className="h-full overflow-hidden"
                >
                  <BlocklyEditor />
                </div>
              </>
            )}
          </div>

          <BottomBar />
          <Footer />
        </>
      ) : (
        <>
          <DocsPanel />
          <Footer />
        </>
      )}
    </div>
  );
}
