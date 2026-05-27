let cache = {
  data: null,
  ts: 0
};

const TTL = 2 * 60 * 60 * 1000; // 2 hours

module.exports = async (req, res) => {

  try {

    // Serve cached data if still valid
    if (cache.data && Date.now() - cache.ts < TTL) {

      return res.status(200).json(cache.data);

    }

    // Fetch broader Texas security jobs
    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security&location=Texas&per_page=50&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    // Physical security filtering
    const filteredJobs = data.jobs.filter(job => {

      const title = (job.title || '').toLowerCase();

      // Keep only physical security style jobs
      const isRelevant = (

        title.includes('officer') ||
        title.includes('guard') ||
        title.includes('patrol') ||
        title.includes('loss prevention') ||
        title.includes('lp') ||
        title.includes('unarmed') ||
        title.includes('armed') ||
        title.includes('building') ||
        title.includes('security specialist') ||
        title.includes('security technician')

      );

      // Remove cybersecurity / IT security jobs
      const isExcluded = (

        title.includes('cyber') ||
        title.includes('cloud') ||
        title.includes('application') ||
        title.includes('software') ||
        title.includes('developer') ||
        title.includes('engineer') ||
        title.includes('architect') ||
        title.includes('devsecops') ||
        title.includes('red team') ||
        title.includes('mainframe') ||
        title.includes('ai ') ||
        title.includes('iam') ||
        title.includes('consultant') ||
        title.includes('analyst')

      );

      return isRelevant && !isExcluded;

    });

    // Remove duplicate companies
    const seenCompanies = new Set();

    const uniqueJobs = filteredJobs.filter(job => {

      const company = job.company_name || '';

      if (seenCompanies.has(company)) {
        return false;
      }

      seenCompanies.add(company);

      return true;

    });

    // Return only top 5 jobs
    const result = {
      jobs: uniqueJobs.slice(0, 5)
    };

    // Save cache
    cache = {
      data: result,
      ts: Date.now()
    };

    // Send response
    res.status(200).json(result);

  } catch (error) {

    res.status(500).json({
      error: error.message
    });

  }

};
