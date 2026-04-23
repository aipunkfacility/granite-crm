import React, { useState } from 'react';
import { Company } from '@/lib/types/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

interface CompanyEditDialogProps {
  company: Company;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updates: any) => void;
  isSaving: boolean;
}

export function CompanyEditDialog({ company, isOpen, onClose, onSave, isSaving }: CompanyEditDialogProps) {
  const [formData, setFormData] = useState({
    name: company.name,
    city: company.city || '',
    website: company.website || '',
    address: company.address || '',
    phones: company.phones.join(', '),
    emails: company.emails.join(', '),
    telegram: company.telegram || '',
    whatsapp: company.whatsapp || '',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const updates: Record<string, any> = {};
    if (formData.name !== company.name) updates.name = formData.name;
    if (formData.city !== company.city) updates.city = formData.city;
    if (formData.website !== (company.website || '')) updates.website = formData.website;
    if (formData.address !== (company.address || '')) updates.address = formData.address;

    const phones = formData.phones.split(',').map(p => p.trim()).filter(Boolean);
    if (JSON.stringify(phones) !== JSON.stringify(company.phones)) updates.phones = phones;

    const emails = formData.emails.split(',').map(e => e.trim()).filter(Boolean);
    if (JSON.stringify(emails) !== JSON.stringify(company.emails)) updates.emails = emails;

    const messengers: Record<string, string> = {};
    if (formData.telegram) messengers.telegram = formData.telegram;
    if (formData.whatsapp) messengers.whatsapp = formData.whatsapp;
    if (formData.telegram !== (company.telegram || '') || formData.whatsapp !== (company.whatsapp || '')) {
      updates.messengers = messengers;
    }

    if (Object.keys(updates).length === 0) {
      toast.info('Нет изменений для сохранения');
      onClose();
      return;
    }

    onSave(updates);
    toast.success('Данные отправлены на сохранение');
    onClose();
  };

  const field = (id: string, label: string, key: keyof typeof formData, placeholder?: string) => (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</Label>
      <Input
        id={id}
        value={formData[key]}
        onChange={e => setFormData({ ...formData, [key]: e.target.value })}
        placeholder={placeholder}
        className="h-9"
      />
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-slate-200">
        <div className="p-6 border-b bg-gradient-to-r from-indigo-50 to-white">
          {/* V-05: font-semibold вместо font-bold */}
          <h2 className="text-xl font-semibold text-indigo-900">Редактирование компании</h2>
          <p className="text-sm text-slate-500 mt-0.5">{company.name} · {company.city}</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {field('name', 'Название', 'name')}

          <div className="grid grid-cols-2 gap-3">
            {field('city', 'Город', 'city', 'Москва')}
            {field('website', 'Сайт', 'website', 'https://...')}
          </div>

          {field('address', 'Адрес', 'address', 'ул. Примерная, 1')}
          {field('phones', 'Телефоны (через запятую)', 'phones', '+79001234567, +79007654321')}
          {field('emails', 'Email (через запятую)', 'emails', 'info@site.ru')}

          <div className="pt-3 border-t space-y-3">
            {/* V-07: text-slate-400 → text-slate-500 на лейблах */}
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Мессенджеры</p>
            <div className="grid grid-cols-2 gap-3">
              {field('tg', 'Telegram', 'telegram', '@username или ссылка')}
              {field('wa', 'WhatsApp', 'whatsapp', '+79001234567 или ссылка')}
            </div>
          </div>
        </form>

        <div className="p-5 border-t bg-slate-50 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} type="button">Отмена</Button>
          {/* V-04: убран хардкод bg-indigo-600 — variant="default" теперь indigo через --primary */}
          <Button
            onClick={handleSubmit}
            disabled={isSaving}
          >
            {isSaving ? 'Сохранение...' : 'Сохранить изменения'}
          </Button>
        </div>
      </div>
    </div>
  );
}
