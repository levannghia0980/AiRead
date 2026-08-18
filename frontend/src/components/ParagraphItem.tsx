import React from 'react'

interface ParagraphItemProps {
  htmlContent: string
  paraIdx?: number
}

export const ParagraphItem: React.FC<ParagraphItemProps> = React.memo(({ htmlContent, paraIdx }) => {
  if (!htmlContent || !htmlContent.trim()) return null

  return (
    <p
      data-para-idx={paraIdx}
      className="mb-4 leading-relaxed text-slate-200"
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  )
})

export default ParagraphItem
