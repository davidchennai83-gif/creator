import React from 'react';
import clsx from 'clsx';

interface StatsCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative';
  icon?: React.ReactNode;
}

export const StatsCard: React.FC<StatsCardProps> = ({ title, value, change, changeType, icon }) => {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change && (
            <p className={clsx('text-sm mt-1', changeType === 'positive' ? 'text-green-600' : 'text-red-600')}>
              {change}
            </p>
          )}
        </div>
        <div className="p-3 bg-primary-50 rounded-lg text-primary-600">{icon}</div>
      </div>
    </div>
  );
};
