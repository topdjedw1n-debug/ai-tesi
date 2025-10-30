import {
  AcademicCapIcon,
  DocumentTextIcon,
  SparklesIcon,
  ClockIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'

const features = [
  {
    name: 'AI-Powered Outline Generation',
    description: 'Generate comprehensive thesis outlines with proper structure and academic flow using advanced AI models.',
    icon: DocumentTextIcon,
  },
  {
    name: 'Smart Section Writing',
    description: 'Create detailed sections with proper citations, academic tone, and research-backed content.',
    icon: AcademicCapIcon,
  },
  {
    name: 'Multiple AI Models',
    description: 'Choose from GPT-4, Claude 3.5, and other leading AI models for different writing styles and requirements.',
    icon: SparklesIcon,
  },
  {
    name: 'Time-Saving Automation',
    description: 'Reduce writing time by up to 70% while maintaining high academic standards and quality.',
    icon: ClockIcon,
  },
  {
    name: 'Multi-Language Support',
    description: 'Generate content in Italian, Spanish, Ukrainian, and other languages with native-level quality.',
    icon: GlobeAltIcon,
  },
  {
    name: 'Secure & Private',
    description: 'Your documents are encrypted and stored securely. We never share your academic work.',
    icon: ShieldCheckIcon,
  },
]

export function Features() {
  return (
    <div id="features" className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-primary-600">Everything you need</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Powerful features for academic writing
          </p>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            Our AI-powered platform provides everything you need to create high-quality thesis content 
            efficiently and professionally.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.name} className="flex flex-col">
                <dt className="flex items-center gap-x-3 text-base font-semibold leading-7 text-gray-900">
                  <feature.icon className="h-5 w-5 flex-none text-primary-600" aria-hidden="true" />
                  {feature.name}
                </dt>
                <dd className="mt-4 flex flex-auto flex-col text-base leading-7 text-gray-600">
                  <p className="flex-auto">{feature.description}</p>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  )
}
