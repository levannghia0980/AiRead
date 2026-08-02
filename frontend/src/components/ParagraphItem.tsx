import React from 'react'

interface ParagraphItemProps {
  htmlContent: string
}

export const ParagraphItem: React.FC<ParagraphItemProps> = React.memo(({ htmlContent }) => {
  if (!htmlContent || !htmlContent.trim()) return null

  return (
    <p
      className="mb-4 leading-relaxed text-slate-200"
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  )
})

export default ParagraphItem
