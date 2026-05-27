let cache = {
  data: null,
  ts: 0
};

// Cache jobs for 12 hours
const TTL = 12 * 60 * 60 * 1000;

module.exports = async (req, res) => {

  try {

    // Return cached jobs if still fresh
    if (cache.data && Date.now() - cache.ts < TTL) {

      return res.status(200).json(cache.data);

    }

    // Fetch DFW security jobs
    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security+officer&location=Dallas%2C+TX%2CFrisco%2C+TX%2CRichardson%2C+TX%2CFort+Worth%2C+TX%2CArlington%2C+TX%2CPlano%2C+TX%2CMcKinney%2C+TX%2CDenton%2C+TX&per_page=25&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    // Domains to block due to bad / stale links
    const blockedCompanies = [
  'Methodist Health System',
  'Marriott'
];
   
    // Filter jobs
    const filteredJobs = data.jobs.filter(job => {

      const title = (job.title || '').toLowerCase();

      // Remove blocked domains
      if (blockedDomains.includes(job.domain_name)) {

        return false;

      }

      // Remove cybersecurity / IT security jobs
      return !title.includes('cyber')
        && !title.includes('information')
        && !title.includes('application')
        && !title.includes('software')
        && !title.includes('developer')
        && !title.includes('engineer')
        && !title.includes('architect')
        && !title.includes('devsecops')
        && !title.includes('red team')
        && !title.includes('mainframe')
        && !title.includes('iam')
        && !title.includes('it ')
        && !title.includes('product manager')
        && !title.includes('compliance manager')
        && !title.includes('analyst');

    });

    // Allow only ONE job per employer
    const seenCompanies = new Set();

    const uniqueJobs = filteredJobs.filter(job => {

      const company = (job.company_name || '').toLowerCase();

      if (seenCompanies.has(company)) {

        return false;

      }

      seenCompanies.add(company);

      return true;

    });

    // Return top 5 jobs
    const result = {
      jobs: uniqueJobs.slice(0, 5)
    };

    // Save cache
    cache = {
      data: result,
      ts: Date.now()
    };

    // Return response
    res.status(200).json(result);

  } catch (error) {

    res.status(500).json({
      error: error.message
    });

  }

};
