import { CheckIcon } from '@heroicons/react/24/outline'
import { Button } from '@/components/ui/Button'

const tiers = [
  {
    name: 'Free',
    id: 'tier-free',
    href: '/auth/register',
    priceMonthly: '$0',
    description: 'Perfect for trying out our platform and small projects.',
    features: [
      'Up to 3 documents',
      'Basic AI models',
      'Standard support',
      'PDF export',
      'Basic templates',
    ],
    mostPopular: false,
  },
  {
    name: 'Student',
    id: 'tier-student',
    href: '/auth/register',
    priceMonthly: '$9',
    description: 'Ideal for students working on their thesis or dissertation.',
    features: [
      'Unlimited documents',
      'Premium AI models (GPT-4, Claude 3.5)',
      'Priority support',
      'DOCX & PDF export',
      'Advanced templates',
      'Citation management',
      'Version history',
    ],
    mostPopular: true,
  },
  {
    name: 'Academic',
    id: 'tier-academic',
    href: '/auth/register',
    priceMonthly: '$29',
    description: 'For researchers and academic institutions.',
    features: [
      'Everything in Student',
      'Team collaboration',
      'Custom AI models',
      'API access',
      'White-label options',
      'Advanced analytics',
      'Dedicated support',
    ],
    mostPopular: false,
  },
]

export function Pricing() {
  return (
    <div id="pricing" className="bg-gray-50 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-4xl text-center">
          <h2 className="text-base font-semibold leading-7 text-primary-600">Pricing</h2>
          <p className="mt-2 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            Choose the right plan for your needs
          </p>
        </div>
        <p className="mx-auto mt-6 max-w-2xl text-center text-lg leading-8 text-gray-600">
          Start free and upgrade as you grow. All plans include our core AI writing features.
        </p>
        <div className="isolate mx-auto mt-16 grid max-w-md grid-cols-1 gap-y-8 sm:mt-20 lg:mx-0 lg:max-w-none lg:grid-cols-3 lg:gap-x-8">
          {tiers.map((tier) => (
            <div
              key={tier.id}
              className={`flex flex-col justify-between rounded-3xl bg-white p-8 ring-1 ring-gray-200 xl:p-10 ${
                tier.mostPopular ? 'ring-2 ring-primary-600' : ''
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-x-4">
                  <h3
                    id={tier.id}
                    className={`text-lg font-semibold leading-8 ${
                      tier.mostPopular ? 'text-primary-600' : 'text-gray-900'
                    }`}
                  >
                    {tier.name}
                  </h3>
                  {tier.mostPopular ? (
                    <p className="rounded-full bg-primary-600/10 px-2.5 py-1 text-xs font-semibold leading-5 text-primary-600">
                      Most popular
                    </p>
                  ) : null}
                </div>
                <p className="mt-4 text-sm leading-6 text-gray-600">{tier.description}</p>
                <p className="mt-6 flex items-baseline gap-x-1">
                  <span className="text-4xl font-bold tracking-tight text-gray-900">
                    {tier.priceMonthly}
                  </span>
                  <span className="text-sm font-semibold leading-6 text-gray-600">/month</span>
                </p>
                <ul role="list" className="mt-8 space-y-3 text-sm leading-6 text-gray-600">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex gap-x-3">
                      <CheckIcon className="h-6 w-5 flex-none text-primary-600" aria-hidden="true" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
              <Button
                asChild
                className={`mt-8 ${
                  tier.mostPopular
                    ? 'bg-primary-600 text-white hover:bg-primary-500'
                    : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                }`}
              >
                <a href={tier.href}>
                  Get started today
                </a>
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
