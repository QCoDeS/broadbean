echo "Running the notebooks..."
jupyter nbconvert --to notebook --execute "Pulse Building Tutorial.ipynb"
jupyter nbconvert --to notebook --execute "Filter compensation.ipynb"
jupyter nbconvert --to notebook --execute "Subsequences.ipynb"
echo "Cleaning up the generated output..."
rm *nbconvert.ipynb
