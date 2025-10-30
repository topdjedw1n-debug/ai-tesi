import {
  DocumentPlusIcon,
  SparklesIcon,
  DocumentTextIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline'

const steps = [
  {
    id: 1,
    name: 'Create Your Project',
    description: 'Start by entering your thesis topic, target length, and preferred language. Our system will prepare everything for AI generation.',
    icon: DocumentPlusIcon,
  },
  {
    id: 2,
    name: 'Generate Outline',
    description: 'Our AI analyzes your topic and creates a comprehensive outline with proper academic structure and chapter organization.',
    icon: SparklesIcon,
  },
  {
    id: 3,
    name: 'Write Sections',
    description: 'Generate detailed content for each section with proper citations, academic tone, and research-backed information.',
    icon: DocumentTextIcon,
  },
  {
    id: 4,
    name: 'Export & Share',
    description: 'Download your completed thesis in DOCX or PDF format, ready for submission or further editing.',
    icon: ArrowDownTrayIcon,
  },
]

export function HowItWorks() {
  return (
    <div id="how-it-works" className="bg-white py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-primary-600">How it works</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            From idea to finished thesis in 4 simple steps
          </p>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            Our streamlined process makes thesis writing efficient and stress-free. 
            Get professional results in a fraction of the time.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
            {steps.map((step, stepIdx) => (
              <div key={step.name} className="relative">
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-100">
                    <step.icon className="h-8 w-8 text-primary-600" aria-hidden="true" />
                  </div>
                  <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900">{step.name}</h3>
                    <p className="mt-2 text-base text-gray-600">{step.description}</p>
                  </div>
                </div>
                {stepIdx < steps.length - 1 && (
                  <div className="absolute top-8 left-1/2 hidden h-full w-0.5 -translate-x-1/2 bg-gray-200 lg:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
