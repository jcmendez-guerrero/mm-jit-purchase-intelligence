import { fireEvent, screen, within } from "@testing-library/react";

/** Confirms the open confirmation dialog (its confirm button is the last one). The request sent is the one the screen always sent. */
export function confirmAction(): void {
  const buttons = within(screen.getByRole("dialog")).getAllByRole("button");
  fireEvent.click(buttons[buttons.length - 1]!);
}
