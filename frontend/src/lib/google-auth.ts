const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
const SCOPES = "https://www.googleapis.com/auth/calendar";

export function getGoogleAccessToken(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!window.google?.accounts?.oauth2) {
      reject(
        new Error(
          "Google Identity Services not loaded. Please refresh the page."
        )
      );
      return;
    }

    if (!GOOGLE_CLIENT_ID) {
      reject(new Error("Google Client ID not configured"));
      return;
    }

    let settled = false;

    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: SCOPES,
      callback: (response) => {
        if (settled) return;
        settled = true;
        if (response.error) {
          reject(new Error(response.error));
        } else if (response.access_token) {
          resolve(response.access_token);
        } else {
          reject(new Error("No access token received"));
        }
      },
      // Fires when the popup is closed/dismissed or fails to open, in which
      // case the callback above never runs. Without this the promise would
      // hang forever and the export UI would spin indefinitely.
      error_callback: (error) => {
        if (settled) return;
        settled = true;
        if (error?.type === "popup_closed") {
          reject(
            new Error("Google sign-in was cancelled. Please try again.")
          );
        } else {
          reject(
            new Error(error?.message || "Google sign-in failed. Please try again.")
          );
        }
      },
    });

    client.requestAccessToken();
  });
}
