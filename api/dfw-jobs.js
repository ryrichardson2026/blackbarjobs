let cache = {
  data: null,
  ts: 0
};

const TTL = 2 * 60 * 60 * 1000; // 2 hours

module.exports = async (req, res) => {

  try {

    // Return cached jobs if still fresh
    if (cache.data && Date.now() - cache.ts < TTL) {

      return res.status(200).json(cache.data);

    }

    // Fetch jobs from JobDataLake
    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security%20officer&location=Texas&per_page=50&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    // Remove cybersecurity / IT security jobs
    const filteredJobs = data.jobs.filter(job => {

      const title = (job.title || '').toLowerCase();

      return !title.includes('cyber')
        && !title.includes('information systems')
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

    // Return only top 5 freshest jobs
    const result = {
      jobs: filteredJobs.slice(0, 5)
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
