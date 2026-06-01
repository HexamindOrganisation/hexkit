import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LogOut, Settings as SettingsIcon, User } from "lucide-react";

import { useAuth } from "../auth/AuthContext";


/**
 * Top-right user menu: avatar (initial) + dropdown with Settings + Sign out.
 *
 * Built without a popover library — outside-click and Escape dismissal
 * are the only behaviors that matter, and they're cheap to do by hand.
 */
export function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initial = user?.email?.[0]?.toUpperCase() ?? "?";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-medium hover:bg-muted/80"
        aria-label="User menu"
      >
        {initial}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-48 rounded-md border border-border bg-popover py-1 text-sm shadow-md">
          <div className="border-b border-border px-3 py-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <User className="h-3.5 w-3.5" />
              <span className="truncate">{user?.email ?? "—"}</span>
            </div>
          </div>
          <Link
            to="/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 hover:bg-muted"
          >
            <SettingsIcon className="h-4 w-4" />
            Settings
          </Link>
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
