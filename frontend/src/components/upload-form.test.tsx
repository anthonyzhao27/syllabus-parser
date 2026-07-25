import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ParsedDataProvider } from "@/contexts/parsed-data-context";
import { UploadForm } from "@/components/upload-form";

const mockParseSyllabus = vi.fn();
const mockPush = vi.fn<(href: string) => void>();

vi.mock("@/lib/api", () => ({
  parseSyllabus: (...args: Parameters<typeof mockParseSyllabus>) =>
    mockParseSyllabus(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  return render(<ParsedDataProvider>{ui}</ParsedDataProvider>);
}

describe("UploadForm", () => {
  it("rejects mixed multi-file uploads that are not all images", async () => {
    const user = userEvent.setup();

    renderWithProviders(<UploadForm />);

    const input = document.querySelector('input[type="file"]');

    if (!(input instanceof HTMLInputElement)) {
      throw new Error("File input was not rendered.");
    }

    await user.upload(input, [
      new File(["doc"], "syllabus.pdf", { type: "application/pdf" }),
      new File(["image"], "page-1.png", { type: "image/png" }),
    ]);

    expect(
      screen.getByText(
        "Multiple files are only supported when every file is an image."
      )
    ).toBeInTheDocument();
  });

  it("redirects to the canonical dashboard detail route after parse", async () => {
    const user = userEvent.setup();
    mockParseSyllabus.mockResolvedValue({
      events: [],
      courseCode: "CSC209",
    });

    renderWithProviders(<UploadForm />);

    const input = document.querySelector('input[type="file"]');

    if (!(input instanceof HTMLInputElement)) {
      throw new Error("File input was not rendered.");
    }

    await user.upload(
      input,
      new File(["doc"], "syllabus.pdf", { type: "application/pdf" })
    );

    await user.click(screen.getByRole("button", { name: /parse syllabus/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/results");
    });
  });
});
