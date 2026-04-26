export function Footer() {
  const year = new Date().getFullYear();
  
  return (
    <footer className="bg-gray-200 border-t border-gray-300 px-4 py-1 flex items-center justify-between text-xs text-gray-500 shrink-0">
      <div className="flex items-center gap-2">
        <span>ST3215 Robot Control v2.0.0</span>
        <span>•</span>
        <span>{year}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-gray-400">Powered by FastAPI + React</span>
      </div>
    </footer>
  );
}