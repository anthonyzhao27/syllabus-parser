"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { deleteAccount } from "@/lib/api";
import { Header } from "./header";
import { RequireAuth } from "./require-auth";

const CONFIRM_TOKEN = "DELETE";

export function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}

function SettingsContent() {
  const { user } = useAuth();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openDialog() {
    setConfirmText("");
    setError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    if (deleting) return;
    setDialogOpen(false);
  }

  async function handleDelete() {
    if (confirmText !== CONFIRM_TOKEN) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount();
      window.location.href = "/";
    } catch (err) {
      setDeleting(false);
      setError(
        err instanceof Error
          ? err.message
          : "Account deletion failed. Please try again."
      );
    }
  }

  return (
    <>
      <Header />
      <main className="min-h-screen px-6 py-24 md:px-8">
        <div className="mx-auto max-w-2xl">
          <h1 className="mb-2 font-quicksand text-3xl font-bold text-warm-700 md:text-4xl">
            Settings
          </h1>
          <p className="mb-8 text-sm text-warm-400">
            Manage your account.
          </p>

          <div className="space-y-6">
            <section className="rounded-2xl border border-white/70 bg-white/85 p-6 shadow-sm">
              <h2 className="mb-3 font-quicksand text-lg font-semibold text-warm-700">
                Account
              </h2>
              <div className="text-sm text-warm-500">
                <div className="text-xs uppercase tracking-wide text-warm-400">
                  Signed in as
                </div>
                <div className="mt-1 font-medium text-warm-700">
                  {user?.email ?? "Unknown"}
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-red-200 bg-white/85 p-6 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-error" />
                <h2 className="font-quicksand text-lg font-semibold text-error">
                  Danger zone
                </h2>
              </div>
              <p className="mb-4 text-sm text-warm-500">
                Permanently delete your account and all associated data:
                uploaded syllabi, extracted events, and your profile. This
                action cannot be undone.
              </p>
              <button
                type="button"
                onClick={openDialog}
                className="rounded-xl bg-error px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-red-600"
              >
                Delete account
              </button>
            </section>
          </div>
        </div>
      </main>

      <DeleteAccountDialog
        isOpen={dialogOpen}
        confirmText={confirmText}
        onConfirmTextChange={setConfirmText}
        onCancel={closeDialog}
        onConfirm={handleDelete}
        deleting={deleting}
        error={error}
      />
    </>
  );
}

type DialogProps = {
  isOpen: boolean;
  confirmText: string;
  onConfirmTextChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  deleting: boolean;
  error: string | null;
};

function DeleteAccountDialog({
  isOpen,
  confirmText,
  onConfirmTextChange,
  onCancel,
  onConfirm,
  deleting,
  error,
}: DialogProps) {
  if (typeof window === "undefined") return null;

  const canConfirm = confirmText === CONFIRM_TOKEN && !deleting;

  return createPortal(
    <AnimatePresence>
      {isOpen ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onCancel}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-warm-900">
              Delete account
            </h2>
            <p className="mt-2 text-sm text-warm-600">
              This will permanently delete your account, all uploaded syllabi,
              and all extracted events. This cannot be undone.
            </p>
            <p className="mt-4 text-sm text-warm-700">
              Type <span className="font-mono font-semibold">{CONFIRM_TOKEN}</span> to confirm:
            </p>
            <input
              type="text"
              autoFocus
              value={confirmText}
              onChange={(e) => onConfirmTextChange(e.target.value)}
              disabled={deleting}
              className="mt-2 w-full rounded-xl border border-warm-200 bg-white px-3 py-2 text-sm text-warm-700 outline-none transition-colors focus:border-error disabled:opacity-60"
              placeholder={CONFIRM_TOKEN}
            />
            {error ? (
              <p className="mt-3 text-sm text-error">{error}</p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={onCancel}
                disabled={deleting}
                className="rounded-xl bg-warm-100 px-4 py-2 text-sm font-medium text-warm-700 transition-colors hover:bg-warm-200 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={!canConfirm}
                className="rounded-xl bg-error px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete account"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body
  );
}
