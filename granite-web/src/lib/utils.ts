import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { toast } from "sonner"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function copyToClipboard(text: string, label?: string) {
  navigator.clipboard.writeText(text).then(() => {
    toast.success(`Скопировано: ${label || text}`)
  }).catch(() => {
    toast.error("Не удалось скопировать")
  })
}
