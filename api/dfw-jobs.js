let cache = {
  data: null,
  ts: 0
};

const TTL = 2 * 60 * 60 * 1000; // 2 hours

module.exports = async (req, res) => {

  try {

    // Return cached response if fresh
    if (cache.data && Date.now() - cache.ts < TTL) {

      return res.status(200).json(cache.data);

    }

    // Fetch broader DFW security jobs
    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security&location=Dallas,Fort Worth,Arlington,Plano,Irving,Frisco,Grand Prairie,Mesquite,Richardson,Garland&per_page=50&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    // Filter for physical security jobs only
    const filteredJobs = data.jobs.filter(job => {

      const title = (job.title || '').toLowerCase();

      return (

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

      )

      // Exclude cybersecurity / IT jobs
      && !title.includes('cyber')
      && !title.includes('cloud')
      && !title.includes('application')
      && !title.includes('software')
      && !title.includes('developer')
      && !title.includes('engineer')
      && !title.includes('architect')
      && !title.includes('devsecops')
      && !title.includes('red team')
      && !title.includes('mainframe')
      && !title.includes('ai ')
      && !title.includes('iam')
      && !title.includes('consultant')
      && !title.includes('analyst');

    });

    // Remove duplicate companies if desired
    const seenCompanies = new Set();

    const uniqueJobs = filteredJobs.filter(job => {

      if (seenCompanies.has(job.company_name)) {
        return false;
      }

      seenCompanies.add(job.company_name);

      return true;

    });

    // Limit homepage feed
    const result = {
      jobs: uniqueJobs.slice(0, 5)
    };

    // Save cache
    cache = {
      data: result,
      ts: Date.now()
    };

    // Return jobs
    res.status(200).json(result);

  } catch (error) {

    res.status(500).json({
      error: error.message
    });

  }

};
