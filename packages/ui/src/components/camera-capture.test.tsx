// This project was developed with assistance from AI tools.

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CameraCapture } from './camera-capture';

function getButton(): HTMLElement {
    return screen.getByRole('button', { name: '拍照上传' });
}

describe('CameraCapture', () => {
    beforeEach(() => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia: vi.fn() },
            writable: true,
            configurable: true,
        });
        // Simulate mobile device so the component renders
        window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    });

    it('should render camera button', () => {
        render(<CameraCapture onCapture={vi.fn()} />);
        expect(getButton()).toBeInTheDocument();
    });

    it('should render as disabled when disabled prop is true', () => {
        render(<CameraCapture onCapture={vi.fn()} disabled />);
        expect(getButton()).toBeDisabled();
    });

    it('should open dialog on click', () => {
        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(getButton());
        expect(screen.getByText('拍摄申请材料')).toBeInTheDocument();
    });

    it('should request rear camera when dialog opens', async () => {
        const mockStream = {
            getTracks: () => [{ stop: vi.fn() }],
        } as unknown as MediaStream;
        const getUserMedia = vi.fn().mockResolvedValue(mockStream);
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(getButton());

        await waitFor(() => {
            expect(getUserMedia).toHaveBeenCalledWith({
                video: {
                    facingMode: 'environment',
                    width: { ideal: 2048 },
                    height: { ideal: 1536 },
                    advanced: [{ focusMode: 'continuous' }],
                },
            });
        });
    });

    it('should show error when camera permission is denied', async () => {
        const getUserMedia = vi.fn().mockRejectedValue(
            new DOMException('Permission denied', 'NotAllowedError'),
        );
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(getButton());

        expect(
            await screen.findByText('无法使用相机，请检查相机权限。'),
        ).toBeInTheDocument();
    });

    it('should show generic error when camera fails', async () => {
        const getUserMedia = vi.fn().mockRejectedValue(new Error('Unknown'));
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(getButton());

        expect(
            await screen.findByText('无法访问相机。'),
        ).toBeInTheDocument();
    });

    it('should stop stream tracks when dialog is closed', async () => {
        const stopTrack = vi.fn();
        const mockStream = {
            getTracks: () => [{ stop: stopTrack }],
        } as unknown as MediaStream;
        const getUserMedia = vi.fn().mockResolvedValue(mockStream);
        Object.defineProperty(navigator, 'mediaDevices', {
            value: { getUserMedia },
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        fireEvent.click(getButton());
        await waitFor(() => expect(getUserMedia).toHaveBeenCalled());

        fireEvent.click(screen.getByLabelText('关闭'));
        await waitFor(() => expect(stopTrack).toHaveBeenCalled());
    });

    it('should render native file input fallback when getUserMedia is unavailable', () => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: undefined,
            writable: true,
            configurable: true,
        });

        render(<CameraCapture onCapture={vi.fn()} />);
        expect(getButton()).toBeInTheDocument();
        expect(document.querySelector('input[capture="environment"]')).toBeInTheDocument();
    });

    it('should call onCapture when a file is selected via native input', () => {
        Object.defineProperty(navigator, 'mediaDevices', {
            value: undefined,
            writable: true,
            configurable: true,
        });

        const onCapture = vi.fn();
        render(<CameraCapture onCapture={onCapture} />);

        const fileInput = document.querySelector('input[capture="environment"]') as HTMLInputElement;
        const file = new File(['test'], 'photo.jpg', { type: 'image/jpeg' });
        Object.defineProperty(fileInput, 'files', { value: [file] });
        fireEvent.change(fileInput);

        expect(onCapture).toHaveBeenCalledWith(file);
    });
});
