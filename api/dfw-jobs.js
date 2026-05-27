const blockedCompanies = [
  'Methodist Health System',
  'Marriott'
];

// Filter jobs
const filteredJobs = data.jobs.filter(job => {

  const title = (job.title || '').toLowerCase();

  // Remove blocked companies
  if (blockedCompanies.includes(job.company_name)) {

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
