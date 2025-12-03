/**
 * Tests for StatsGrid component
 * Tests platform statistics display
 */

import { render, screen } from '@testing-library/react';
import { StatsGrid } from '@/components/admin/dashboard/StatsGrid';
import { PlatformStats } from '@/lib/api/admin';

describe('StatsGrid Component', () => {
  const mockStats: PlatformStats = {
    total_users: 1234,
    active_users_today: 56,
    total_revenue: 12345.67,
    revenue_today: 234.50,
    total_documents: 5678,
    completed_documents: 4321,
    pending_refunds: 3,
    active_jobs: 12,
  };

  describe('Stats Display', () => {
    it('displays all platform stats correctly', () => {
      render(<StatsGrid stats={mockStats} />);

      // Check Total Users (uses toLocaleString)
      expect(screen.getByText('Total Users')).toBeInTheDocument();
      expect(screen.getByText('1,234')).toBeInTheDocument();
      expect(screen.getByText('56 active today')).toBeInTheDocument();

      // Check Total Revenue (uses toLocaleString)
      expect(screen.getByText('Total Revenue')).toBeInTheDocument();
      expect(screen.getByText('€12,345.67')).toBeInTheDocument();
      expect(screen.getByText('€234.5 today')).toBeInTheDocument();

      // Check Documents (uses toLocaleString)
      expect(screen.getByText('Documents')).toBeInTheDocument();
      expect(screen.getByText('5,678')).toBeInTheDocument();
      expect(screen.getByText('4321 completed')).toBeInTheDocument();

      // Check Pending Refunds
      expect(screen.getByText('Pending Refunds')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('12 active jobs')).toBeInTheDocument();
    });

    it('renders stat cards with correct styling', () => {
      const { container } = render(<StatsGrid stats={mockStats} />);

      // Check grid layout
      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-1', 'sm:grid-cols-2', 'lg:grid-cols-4');

      // Check stat cards
      const cards = container.querySelectorAll('.bg-gray-800');
      expect(cards.length).toBe(4);
    });

    it('displays icons for each stat category', () => {
      const { container } = render(<StatsGrid stats={mockStats} />);

      // Check for icon letters (U, €, D, R)
      expect(screen.getByText('U')).toBeInTheDocument(); // Users
      expect(screen.getByText('€')).toBeInTheDocument(); // Revenue
      expect(screen.getByText('D')).toBeInTheDocument(); // Documents
      expect(screen.getByText('R')).toBeInTheDocument(); // Refunds
    });
  });

  describe('Number Formatting', () => {
    it('formats large numbers with toLocaleString', () => {
      const largeStats: PlatformStats = {
        total_users: 1234567,
        active_users_today: 12345,
        total_revenue: 9876543.21,
        revenue_today: 54321.00,
        total_documents: 999999,
        completed_documents: 888888,
        pending_refunds: 100,
        active_jobs: 500,
      };

      render(<StatsGrid stats={largeStats} />);

      // Check formatted numbers
      expect(screen.getByText('1,234,567')).toBeInTheDocument();
      expect(screen.getByText('€9,876,543.21')).toBeInTheDocument();
      expect(screen.getByText('999,999')).toBeInTheDocument();
    });

    it('handles zero values correctly', () => {
      const zeroStats: PlatformStats = {
        total_users: 0,
        active_users_today: 0,
        total_revenue: 0,
        revenue_today: 0,
        total_documents: 0,
        completed_documents: 0,
        pending_refunds: 0,
        active_jobs: 0,
      };

      render(<StatsGrid stats={zeroStats} />);

      // Check zero values are displayed (multiple zeros exist, so check specific text)
      expect(screen.getByText('0 active today')).toBeInTheDocument();
      expect(screen.getByText('0 completed')).toBeInTheDocument();
      expect(screen.getByText('0 active jobs')).toBeInTheDocument();
      expect(screen.getByText('€0')).toBeInTheDocument();
    });
  });

  describe('Responsive Layout', () => {
    it('applies correct responsive grid classes', () => {
      const { container } = render(<StatsGrid stats={mockStats} />);

      const grid = container.querySelector('.grid');
      expect(grid).toHaveClass('gap-5');
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('sm:grid-cols-2');
      expect(grid).toHaveClass('lg:grid-cols-4');
    });
  });
});
