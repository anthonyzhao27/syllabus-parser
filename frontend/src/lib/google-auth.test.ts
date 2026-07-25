import { afterEach, describe, expect, it } from "vitest";
import { getGoogleAccessToken } from "@/lib/google-auth";

type TokenCallback = (response: {
  access_token?: string;
  error?: string;
}) => void;
type ErrorCallback = (error: { type?: string; message?: string }) => void;

interface MockTokenClientConfig {
  client_id: string;
  scope: string;
  callback: TokenCallback;
  error_callback?: ErrorCallback;
}

/**
 * Installs a fake Google Identity Services client. `onRequest` is invoked when
 * requestAccessToken() is called, letting each test drive the success/error
 * callbacks however it likes.
 */
function mockGoogle(
  onRequest: (config: MockTokenClientConfig) => void
): void {
  (window as unknown as { google?: unknown }).google = {
    accounts: {
      oauth2: {
        initTokenClient: (config: MockTokenClientConfig) => ({
          requestAccessToken: () => onRequest(config),
        }),
      },
    },
  };
}

afterEach(() => {
  delete (window as unknown as { google?: unknown }).google;
});

describe("getGoogleAccessToken", () => {
  it("resolves with the access token on success", async () => {
    mockGoogle((config) => {
      config.callback({ access_token: "token-123" });
    });

    await expect(getGoogleAccessToken()).resolves.toBe("token-123");
  });

  it("rejects when the popup is closed/dismissed", async () => {
    mockGoogle((config) => {
      config.error_callback?.({ type: "popup_closed" });
    });

    await expect(getGoogleAccessToken()).rejects.toThrow(
      /cancelled/i
    );
  });

  it("rejects on a generic popup/error_callback failure", async () => {
    mockGoogle((config) => {
      config.error_callback?.({ type: "popup_failed_to_open" });
    });

    await expect(getGoogleAccessToken()).rejects.toThrow(
      /failed/i
    );
  });

  it("rejects when the token callback reports an error", async () => {
    mockGoogle((config) => {
      config.callback({ error: "access_denied" });
    });

    await expect(getGoogleAccessToken()).rejects.toThrow("access_denied");
  });

  it("only settles once even if both callbacks fire", async () => {
    let savedConfig: MockTokenClientConfig | undefined;
    mockGoogle((config) => {
      savedConfig = config;
      config.callback({ access_token: "token-abc" });
    });

    const promise = getGoogleAccessToken();
    // A late error_callback (e.g. popup closing after success) must not flip
    // an already-resolved promise into a rejection.
    savedConfig?.error_callback?.({ type: "popup_closed" });

    await expect(promise).resolves.toBe("token-abc");
  });

  it("rejects when Google Identity Services is not loaded", async () => {
    delete (window as unknown as { google?: unknown }).google;

    await expect(getGoogleAccessToken()).rejects.toThrow(
      /not loaded/i
    );
  });
});
