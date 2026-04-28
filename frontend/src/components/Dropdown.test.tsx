import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Dropdown from './Dropdown';

const OPTIONS = [
  { value: '', label: 'Все' },
  { value: 'a', label: 'Option A', tone: 'blue' as const },
  { value: 'b', label: 'Option B', tone: 'green' as const },
];

describe('Dropdown', () => {
  it('shows the currently selected label on the trigger', () => {
    render(<Dropdown value="a" onChange={() => {}} options={OPTIONS} />);
    expect(screen.getByRole('button', { name: /Option A/ })).toBeInTheDocument();
  });

  it('opens the listbox on click and shows all options', async () => {
    const ue = userEvent.setup();
    render(<Dropdown value="" onChange={() => {}} options={OPTIONS} />);

    expect(screen.queryByRole('listbox')).toBeNull();

    await ue.click(screen.getByRole('button', { name: /Все/ }));

    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('calls onChange with the picked value and closes the listbox', async () => {
    const onChange = vi.fn();
    const ue = userEvent.setup();
    render(<Dropdown value="" onChange={onChange} options={OPTIONS} />);

    await ue.click(screen.getByRole('button', { name: /Все/ }));
    await ue.click(screen.getByRole('option', { name: 'Option B' }));

    expect(onChange).toHaveBeenCalledWith('b');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('closes when the user clicks outside', async () => {
    const ue = userEvent.setup();
    render(
      <div>
        <Dropdown value="" onChange={() => {}} options={OPTIONS} />
        <span data-testid="outside">outside</span>
      </div>
    );

    await ue.click(screen.getByRole('button', { name: /Все/ }));
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    await ue.click(screen.getByTestId('outside'));
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('closes on Escape', async () => {
    const ue = userEvent.setup();
    render(<Dropdown value="" onChange={() => {}} options={OPTIONS} />);

    await ue.click(screen.getByRole('button', { name: /Все/ }));
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    await ue.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('applies tone classes to options that declare one', async () => {
    const ue = userEvent.setup();
    render(<Dropdown value="" onChange={() => {}} options={OPTIONS} />);

    await ue.click(screen.getByRole('button', { name: /Все/ }));

    const optionA = screen.getByRole('option', { name: 'Option A' });
    expect(optionA.className).toMatch(/bg-blue-50/);

    const optionB = screen.getByRole('option', { name: 'Option B' });
    expect(optionB.className).toMatch(/bg-green-50/);
  });
});
