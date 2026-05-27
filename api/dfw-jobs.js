let cache = {
  data: null,
  ts: 0
};

const TTL = 2 * 60 * 60 * 1000; // 2 hours

module.exports = async (req, res) => {

  try {

    // Return cached data if still valid
    if (cache.data && Date.now() - cache.ts < TTL) {

      return res.status(200).json(cache.data);

    }

    // Fetch fresh jobs
    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security+officer&location=Dallas&per_page=10&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    // Filter out irrelevant tech/security jobs
    const filteredJobs = data.jobs.filter(job => {

      const title = (job.title || '').toLowerCase();

      return !title.includes('cloud')
        && !title.includes('cyber')
        && !title.includes('architect')
        && !title.includes('engineer')
        && !title.includes('information security')
        && !title.includes('devsecops')
        && !title.includes('application security')
        && !title.includes('infosec');

    });

    // Limit to top 5 freshest jobs
    const result = {
      jobs: filteredJobs.slice(0, 5)
    };

    // Save to cache
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
