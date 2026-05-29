import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

interface AddCompanyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    name: string;
    city: string;
    region?: string;
    phones?: string[];
    emails?: string[];
    website?: string;
    address?: string;
    messengers?: Record<string, string>;
  }) => void;
  isSaving: boolean;
}

export function AddCompanyDialog({ isOpen, onClose, onSave, isSaving }: AddCompanyDialogProps) {
  const [formData, setFormData] = useState({
    name: '',
    city: '',
    website: '',
    address: '',
    phones: '',
    emails: '',
    telegram: '',
    whatsapp: '',
    vk: '',
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error('Название компании обязательно');
      return;
    }
    if (!formData.city.trim()) {
      toast.error('Город обязателен');
      return;
    }

    const phones = formData.phones.split(',').map(p => p.trim()).filter(Boolean);
    const emails = formData.emails.split(',').map(e => e.trim()).filter(Boolean);
    const messengers: Record<string, string> = {};
    if (formData.telegram) messengers.telegram = formData.telegram;
    if (formData.whatsapp) messengers.whatsapp = formData.whatsapp;
    if (formData.vk) messengers.vk = formData.vk;

    onSave({
      name: formData.name.trim(),
      city: formData.city.trim(),
      website: formData.website || undefined,
      address: formData.address || undefined,
      phones: phones.length ? phones : undefined,
      emails: emails.length ? emails : undefined,
      messengers: Object.keys(messengers).length ? messengers : undefined,
    });
  };

  const field = (id: string, label: string, key: keyof typeof formData, placeholder?: string) => (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</Label>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-border">
        <div className="p-6 border-b bg-gradient-to-r from-primary/10 to-card">
          <h2 className="text-xl font-semibold text-primary">Добавление компании</h2>
          <p className="text-sm text-muted-foreground mt-0.5">Заполните данные новой компании</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {field('name', 'Название *', 'name')}

          <div className="grid grid-cols-2 gap-3">
            {field('city', 'Город *', 'city', 'Москва')}
            {field('website', 'Сайт', 'website', 'https://...')}
          </div>

          {field('address', 'Адрес', 'address', 'ул. Примерная, 1')}
          {field('phones', 'Телефоны (через запятую)', 'phones', '+79001234567, +79007654321')}
          {field('emails', 'Email (через запятую)', 'emails', 'info@site.ru')}

          <div className="pt-3 border-t space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Мессенджеры</p>
            <div className="grid grid-cols-3 gap-3">
              {field('tg', 'Telegram', 'telegram', '@username или ссылка')}
              {field('wa', 'WhatsApp', 'whatsapp', '+79001234567 или ссылка')}
              {field('vk', 'VK', 'vk', 'vk.com/...')}
            </div>
          </div>
        </form>

        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} type="button">Отмена</Button>
          <Button onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Создание...' : 'Создать компанию'}
          </Button>
        </div>
      </div>
    </div>
  );
}
